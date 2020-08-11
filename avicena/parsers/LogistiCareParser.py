import PyPDF2
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from datetime import datetime
import pandas as pd
import numpy as np
import csv
import re
import os

from avicena.util.Geolocator import find_coord_lat_lon
from avicena.util.TimeWindows import get_time_window_by_hours_minutes
from avicena.util.optimizer_util import convert_time


def _load_pdf_content(pdf):
    #################################
    ##        Load content         ##
    #################################
    # Discerning the number of pages will allow us to parse through all #the pages
    num_pages = pdf.numPages
    count = 0
    text = ""
    # The while loop will read each page
    while count < num_pages:
        pageObj = pdf.getPage(count)
        count += 1
        text += pageObj.extractText()
    # This if statement exists to check if the above library returned #words. It's done because PyPDF2 cannot read scanned files.
    if text != "":
        text = text
    # If the above returns as False, we run the OCR library textract to #convert scanned/image based PDF files into text
    else:
        print('cannot read scanned images.')
    return text


def _remove_adjacent(nums):
    result = []
    for num in nums:
        if len(result) == 0 or num != result[-1]:
            result.append(num)
    return result


def _tokenize_text(text):
    #################################
    ##      Tokenize content       ##
    #################################
    # The word_tokenize() function will break our text phrases into #individual words
    tripCount = text.count('Age:')
    tokens = word_tokenize(text)
    for index, x in enumerate(tokens):
        if (x == '--') & (tokens[index - 1] == '--'):
            tokens[index] = 'newline'
    tokens = _remove_adjacent(tokens)
    tokens.append('newline')
    return tokens, tripCount


def _initialize_df(tokens):
    #################################
    ##   Split content into rows   ##
    #################################
    list1 = []
    list2 = []
    for index, x in enumerate(tokens):
        if x != 'newline':
            list1.append(x)
        elif x == 'newline':
            list1 = ' '.join(list1)
            list2.append(list1)
            list1 = []
    se = pd.Series(list2)
    df = pd.DataFrame()
    df['raw_data'] = se.values
    df = df[df["raw_data"] != '--']
    for index, row in df.iterrows():
        searchString = row['raw_data']
        if "LogistiCare" in searchString:
            y = searchString.find("LogistiCare")
            row['raw_data'] = row['raw_data'][:y]
        searchString = row['raw_data']
        searchString = searchString.replace('-- ', '')
        row['raw_data'] = searchString
    cols = df.columns.tolist()
    cols = cols[-1:] + cols[:-1]
    df = df[cols]
    df = df.iloc[1:]
    return df


def _split_it(raw_data):
    return re.search(
        r"(.*?) \*\* (.*?) \*\* .*? (\d{2}:\d{2}) PU .*? Phy : .{16} (.*?) (\d{2}:\d{2}) DO .*? (.*?) LOS : (\S+) .*? Miles : (\d*).*$",
        raw_data)


def _adjust_pickup_dropoff_merge(pickup_time, id, pickup_address, dropoff_times, ids, config):
    id_mapping = {'B': 'A', 'C': 'B'}
    is_merge = any(ad in pickup_address for ad in config['merge_addresses'])
    start_window = config['merge_window'] if is_merge else get_time_window_by_hours_minutes(2, 30)
    end_window = get_time_window_by_hours_minutes(2, 0)
    if pickup_time == 0.0 or pickup_time > 1 - (1 / 24) and (id.endswith('B') or id.endswith('C')):
        pickup_time = dropoff_times[ids == id[:-1] + id_mapping[id[-1]]].iloc[0] + start_window
        return pickup_time, min(1 - (1 / 24), pickup_time + end_window), is_merge
    else:
        return pickup_time, min(1 - (1 / 24), pickup_time + end_window), is_merge


def _clean_address(addr):
    replacements = {'No Gc': '', '*': '', 'Apt. ': '', '//': '', 'Bldg .': '', 'Aust ': 'Austin, TX ', 'B': 'Blvd'}
    for to_replace, replace_with in replacements.items():
        pattern = re.compile(r"\s+" + re.escape(to_replace) + r"\s+")
        addr = re.sub(pattern, replace_with, addr)
    return addr


def _load_revenue_table(rev_table_file):
    rev_df = pd.read_csv(rev_table_file)
    table = {'A':dict(), 'W':dict(), 'A-EP':dict(), 'W-EP':dict()}
    for typ in table:
        details = rev_df[['Miles', typ]]
        for _, row in details.iterrows():
            table[typ][row['Miles']] = float(row[typ])
    return table


def _revenue_calculation(table, miles, los):
    rates = table[los]
    if miles < 4:
        return rates['0']
    elif miles < 7:
        return rates['4']
    elif miles < 10:
        return rates['7']
    else:
        return rates['10'] + rates['>10'] * (miles - 10)


def pdf2csv(trips_pdf, rev_table_csv, outputDir, config):
    z = trips_pdf.find(".pdf")
    name = trips_pdf[trips_pdf.rfind('/') + 1:z]
    pdfFileObj = open(trips_pdf, 'rb')
    loaded_pdf = PyPDF2.PdfFileReader(pdfFileObj)
    text = _load_pdf_content(loaded_pdf)
    # Now we have a text variable which contains all the text derived #from our PDF file. Type print(text) to see what it contains. It #likely contains a lot of spaces, possibly junk such as '\n' etc.
    tokens, tripCount = _tokenize_text(text)
    df = _initialize_df(tokens)
    #################################
    ## Split raw_data into columns ##
    #################################
    df['trip_id'] = df['raw_data'].apply(lambda x: _split_it(x).group(1))
    df['trip_status'] = df['raw_data'].apply(lambda x: _split_it(x).group(2))
    df['trip_pickup_time'] = df['raw_data'].apply(lambda x: convert_time(_split_it(x).group(3)))
    df['trip_pickup_address'] = df['raw_data'].apply(lambda x: _clean_address(_split_it(x).group(4)))
    df['trip_dropoff_time'] = df['raw_data'].apply(lambda x: convert_time(_split_it(x).group(5)))
    df['trip_dropoff_address'] = df['raw_data'].apply(lambda x: _clean_address(_split_it(x).group(6)))
    df['trip_los'] = df['raw_data'].apply(lambda x: _split_it(x).group(7))
    df['trip_miles'] = df['raw_data'].apply(lambda x: int(_split_it(x).group(8)))
    df['trip_pickup_time', 'trip_dropoff_time', 'merge_flags'] = \
        df[['trip_pickup_time', 'trip_id', 'trip_pickup_address']].apply(
            lambda x: _adjust_pickup_dropoff_merge(x['trip_pickup_time'], x['trip_id'], x['trip_pickup_address'],
                                                   df['trip_dropoff_time'], df['trip_id'], config), axis=1)
    revenue_table = _load_revenue_table(rev_table_csv)
    df['trip_revenue'] = df[['trip_miles', 'trip_los']].apply(lambda x: _revenue_calculation(revenue_table, x['trip_miles'], x['trip_los']), axis=1)
    df['trip_pickup_lat', 'trip_pickup_lon'] = df['trip_pickup_address'].apply(lambda x: find_coord_lat_lon(x, config['geo_key']))
    df['trip_dropoff_lat', 'trip_dropoff_lon'] = df['trip_dropoff_address'].apply(lambda x: find_coord_lat_lon(x, config['geo_key']))
    s = (tokens[10] + ' ' + tokens[11] + tokens[12] + ' ' + tokens[13])
    d = datetime.strptime(s, '%B %d, %Y')
    filedate1 = d.strftime('%m/%d/%y')
    df['date'] = filedate1
    print(str(len(df)) + "/" + str(tripCount) + " trips parsed.")
    filedate = filedate1.replace('/', '_')
    df.drop('raw_data', axis='columns')
    df.to_csv(outputDir + name + filedate + '.csv', encoding='utf-8', index=False)
    print('PDF file converted to ' + outputDir + name + filedate + '.csv')
    return outputDir + name + filedate + '.csv'

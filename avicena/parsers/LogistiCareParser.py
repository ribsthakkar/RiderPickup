from typing import List, Optional, Match, AnyStr, Dict

from PyPDF2 import PdfFileReader
from nltk.tokenize import word_tokenize
from datetime import datetime
import pandas as pd
import re
import os

from pandas import DataFrame

from avicena.models import MergeAddress, RevenueRate
from avicena.util.Geolocator import locations
from avicena.util.ParserUtil import standardize_trip_df


def _load_pdf_content(pdf: PdfFileReader) -> str:
    """
    #################################
    ##        PDF Load content         ##
    #################################
    :param pdf: PDFFileReader object that has loaded the PDF path
    :return: the raw text from the PDF
    """

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


def _tokenize_text(text: str) -> (List[str], int):
    """
    #################################
    ##      Tokenize content       ##
    #################################
    # The word_tokenize() function will break our text phrases into #individual words
    :param text: Parsed Text
    :return: Break up the text into a list of words and return the total number of trips
    """

    def _remove_adjacent(nums):
        result = []
        for num in nums:
            if len(result) == 0 or num != result[-1]:
                result.append(num)
        return result

    trip_count = text.count('Age:')
    tokens = word_tokenize(text)
    for index, x in enumerate(tokens):
        if (x == '--') & (tokens[index - 1] == '--'):
            tokens[index] = 'newline'
    tokens = _remove_adjacent(tokens)
    tokens.append('newline')
    return tokens, trip_count


def _initialize_df(tokens: List[str]) -> DataFrame:
    """
    #################################
    ##   Split content into rows   ##
    #################################
    :param tokens: list of string tokens extracted from PDF
    :return: A dataframe of rows filled with a single column "raw_data" for each trip to be completed
    """

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


def _split_it(raw_data) -> Optional[Match[AnyStr]]:
    """
    Apply Regex to the raw data column and split it into groups
    :param raw_data: raw data string
    :return: A Regex Match
    """
    return re.search(
        r"(.*?) \*\* (.*?) \*\* (.*?) - (.*?) (.*?) Age : (.*?) (\d{2}:\d{2}) PU (.*?) Phy : (.{16}) (.*?) (\d{2}:\d{2}) DO (.*?) Phy : (.{16}) (.*?) LOS : (\S+) (.*?(?=CPay))CPay : (.*?) PCA : (.*?) AEsc : (.*?) CEsc : (.*?) Seats : (.*?) Miles : (\d*)(.*$)",
        raw_data)


def _clean_address(addr: str) -> str:
    """
    Remove clobbering tokens from input address
    :param addr: Address with unneeded tokens
    :return: cleandup address string
    """
    replacements = {'No Gc': ' ', '*': ' ', '\s*Apt. ': ' ', '//': ' ', 'Bldg .': ' ', 'Aust ': 'Austin, TX ',
                    ' B ': 'Blvd ', 'Doorcode :': ' '}
    for to_replace, replace_with in replacements.items():
        pattern = re.compile(r"\s*" + re.escape(to_replace) + r"\s*")
        addr = re.sub(pattern, replace_with, addr)
    return addr


def _parse_raw_data(df: DataFrame, tokens: List[str]) -> None:
    """
    Split the 'raw_data' column in the dataframe and populate it with individual details of each column
    :param df: DataFrame with `raw_data` column parsed from PDF
    :param tokens: Raw Tokens from the PDF
    """
    #################################
    ## Split raw_data into columns ##
    #################################
    df['trip_id'] = df['raw_data'].apply(lambda x: _split_it(x).group(1))
    df['trip_status'] = df['raw_data'].apply(lambda x: _split_it(x).group(2))
    df['trip_reg'] = df['raw_data'].apply(lambda x: _split_it(x).group(3))
    df['trip_county'] = df['raw_data'].apply(lambda x: _split_it(x).group(4))
    df['customer_name'] = df['raw_data'].apply(lambda x: _split_it(x).group(5))
    df['customer_age'] = df['raw_data'].apply(lambda x: _split_it(x).group(6))
    df['trip_pickup_time'] = df['raw_data'].apply(lambda x: _split_it(x).group(7))
    df['trip_pickup_name'] = df['raw_data'].apply(lambda x: _split_it(x).group(8))
    df['trip_pickup_phone'] = df['raw_data'].apply(lambda x: _split_it(x).group(9))
    df['trip_pickup_address'] = df['raw_data'].apply(lambda x: _clean_address(_split_it(x).group(10)))
    df['trip_dropoff_time'] = df['raw_data'].apply(lambda x: _split_it(x).group(11))
    df['trip_dropoff_name'] = df['raw_data'].apply(lambda x: _split_it(x).group(12))
    df['trip_dropoff_phone'] = df['raw_data'].apply(lambda x: _split_it(x).group(13))
    df['trip_dropoff_address'] = df['raw_data'].apply(lambda x: _clean_address(_split_it(x).group(14)))
    df['trip_los'] = df['raw_data'].apply(lambda x: _split_it(x).group(15))
    df['trip_daysofweek'] = df['raw_data'].apply(lambda x: _split_it(x).group(16))
    df['trip_cpay'] = df['raw_data'].apply(lambda x: _split_it(x).group(17))
    df['trip_pca'] = df['raw_data'].apply(lambda x: _split_it(x).group(18))
    df['trip_aesc'] = df['raw_data'].apply(lambda x: _split_it(x).group(19))
    df['trip_cesc'] = df['raw_data'].apply(lambda x: _split_it(x).group(20))
    df['trip_seats'] = df['raw_data'].apply(lambda x: _split_it(x).group(21))
    df['trip_miles'] = df['raw_data'].apply(lambda x: _split_it(x).group(22))
    df['trip_notes'] = df['raw_data'].apply(lambda x: _split_it(x).group(23))
    s = (tokens[10] + ' ' + tokens[11] + tokens[12] + ' ' + tokens[13])
    d = datetime.strptime(s, '%B %d, %Y')
    filedate = d.strftime('%m-%d-%y')
    df['trip_date'] = filedate


def _store_raw_data(df: DataFrame, output_directory: str, name: str, trip_count: int) -> None:
    """
    Save the raw parsed data in the directory
    :param df: DataFrame with the raw data split into columns
    :param output_directory: directory where parsed DataFrame will be stored as CSV
    :param name: name of the model run
    :param trip_count: total number of trips found in PDF
    """
    filedate = df['trip_date'].iloc[0].replace('-', '_')
    print(str(len(df)) + "/" + str(trip_count) + " trips parsed.")
    df.to_csv(output_directory + name + filedate + '.csv', encoding='utf-8', index=False)
    print('PDF file converted to ' + output_directory + name + filedate + '.csv')


def parse_trips_to_df(trips_file: str, merge_details: Dict[str, MergeAddress],
                      revenue_table: Dict[str, List[RevenueRate]], output_directory: str) -> DataFrame:
    """
    Parse in the input PDF into a DataFrame with the trip details extracted
    :param trips_file: Path to PDF trips file
    :param merge_details: dictionary mapping address substring to actual MergeAddress object
    :param revenue_table: dictionary mapping level of service to a list of associated revenue rates
    :param output_directory: directory where intermediate parsed files will be stored
    :return: DataFrame with parsed Trip Details
    """
    z = trips_file.find(".pdf")
    name = trips_file[trips_file.rfind('/') + 1:z]
    pdfFileObj = open(trips_file, 'rb')
    loaded_pdf = PdfFileReader(pdfFileObj)
    text = _load_pdf_content(loaded_pdf)
    tokens, trip_count = _tokenize_text(text)
    df = _initialize_df(tokens)
    _parse_raw_data(df, tokens)
    _store_raw_data(df, output_directory, name, trip_count)
    standardize_trip_df(df, merge_details, revenue_table)
    df.drop(['raw_data', 'trip_notes', 'trip_reg', 'trip_county', 'customer_name', 'customer_age', 'trip_pickup_name',
             'trip_pickup_phone', 'trip_dropoff_name', 'trip_dropoff_phone', 'trip_daysofweek', 'trip_cpay', 'trip_pca',
             'trip_aesc', 'trip_cesc', 'trip_seats', 'trip_notes'], axis='columns', inplace=True)
    return df[df['trip_status'] != "CANCELED"]

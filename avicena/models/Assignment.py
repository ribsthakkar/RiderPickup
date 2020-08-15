import random
from typing import Dict, Any, Union, Mapping, Tuple, List

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from pandas import DataFrame, Series
from plotly.subplots import make_subplots

from datetime import datetime, timedelta
from sqlalchemy import Column, Integer, DateTime, String, Interval, Float
from sqlalchemy.dialects.postgresql import ARRAY as Array
from sqlalchemy.orm import relationship, Session

from avicena.models.Driver import Driver
from avicena.models.DriverAssignment import DriverAssignment
from avicena.util.Geolocator import find_coord_lon_lat
from avicena.util.TimeWindows import timedelta_to_hhmmss
from avicena.util.VisualizationUtil import generate_html_label_for_addr, generate_html_label_for_driver_addr
from . import Base


class Assignment(Base):
    """
    This class represents an instance of a Dispatch "Assignment"
    This class primarly stores the general details about the assignment including the list of drivers, the respective
    distances traveled, revenue earned, time of the earliest pickup and the latest dropoff, and the coordinates of all
    locations.
    It also stores a list of DriverAssignments which contains more driver specific details about the dispatch.
    It extends from the SQL Alchemy Base class as the resulting Assignments produced from solving the model are stored
    in the database, if enabled.
    """
    __tablename__ = "assignment"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    name = Column(String)
    driver_assignments = relationship('DriverAssignment', backref='assignment')
    driver_names = Column(Array(String))
    driver_ids = Column(Array(Integer))
    trips = Column(Array(String))
    times = Column(Array(Interval))
    earliest_picks = Column(Array(Interval))
    latest_drops = Column(Array(Interval))
    miles = Column(Array(Float))
    revenues = Column(Array(Float))
    location_lats = Column(Array(Float))
    location_lons = Column(Array(Float))
    location_labels = Column(Array(String))

    def __init__(self, date: datetime, name: str) -> None:
        """
        Initialize an empty assignment
        :param date: Date of the associated dispatch
        :param name: Name of the model
        """
        self.date = date
        self.name = name
        self.driver_assignments = []
        self.driver_names = []
        self.driver_ids = []
        self.trips = []
        self.times = []
        self.earliest_picks = []
        self.latest_drops = []
        self.miles = []
        self.revenues = []
        self.location_lats = []
        self.location_lons = []
        self.location_labels = []

    def serialize(self) -> Dict[str, Any]:
        """
        Generate a simple serialization of the model with just the id, date, and name
        :return: Dict with id, date, and name
        """
        return {"id": self.id,
                "date": self.date,
                "name": self.name}

    def generate_visualization(self, visualization_file_name: str = 'visualized.html',
                               open_in_browser: bool = False) -> None:
        """
        Generate HTML Visualization of the Assignment.
        The visualization contains a map showing each driver's individual route and the set of all locations with
        annotations that list when a driver is expected to visit the location for which trip.
        It also contains a series of tables. The first table is the overall of each driver followed by tables detailing
        each driver's individual route and estimated pickup and dropoff times.
        :param visualization_file_name: Path where generated visualization will be stored
        :param open_in_browser: Open the generated HTML in a browser
        """

        # Prepare Table Setup
        titles = self.driver_names
        titles.insert(0, "Map")
        titles.insert(1, "Driver Summary: " + self.name)
        subplots = [[{"type": "table"}]] * (len(self.driver_names) + 1)
        subplots.insert(0, [{"type": "scattermapbox"}])
        map_height = 600 / (600 + 2000 + 400 * (len(self.driver_names)))
        summary_height = 600 / (600 + 2000 + 400 * (len(self.driver_names)))
        heights = [(1 - map_height - summary_height - 0.12) / ((len(self.driver_names)))] * (len(self.driver_names))
        heights.insert(0, map_height)
        heights.insert(1, summary_height)
        fig = make_subplots(
            rows=2 + len(self.driver_names), cols=1,
            vertical_spacing=0.015,
            subplot_titles=titles,
            specs=subplots,
            row_heights=heights
        )
        all_lon = []
        all_lat = []

        # Generate Driver Route Tables
        for i, name in enumerate(self.driver_names):
            r = lambda: random.randint(0, 255)
            col = '#%02X%02X%02X' % (r(), r(), r())
            driver_assignment = self.driver_assignments[i]
            details = [driver_assignment.trip_ids,
                       driver_assignment.trip_pu,
                       driver_assignment.trip_do,
                       list(map(timedelta_to_hhmmss, driver_assignment.trip_est_pu)),
                       list(map(timedelta_to_hhmmss, driver_assignment.trip_sch_pu)),
                       list(map(timedelta_to_hhmmss, driver_assignment.trip_est_do)),
                       list(map(timedelta_to_hhmmss, driver_assignment.trip_sch_do)),
                       driver_assignment.trip_miles,
                       driver_assignment.trip_los,
                       driver_assignment.trip_rev]
            all_lon += driver_assignment.lons
            all_lat += driver_assignment.lats
            fig.add_trace(go.Scattermapbox(
                lon=driver_assignment.lons,
                lat=driver_assignment.lats,
                mode='lines',
                marker=dict(
                    size=8,
                    color=col,
                ),
                name=name,

            ), row=1, col=1)
            fig.add_trace(
                go.Table(
                    header=dict(
                        values=["TripID", "Pickup Address", "Dropoff Address", "Estimated Pickup Time",
                                "Scheduled Pickup Time", "Estimated Dropoff Time", "Scheduled Dropoff Time", "Miles",
                                "LOS", "Revenue"],
                        font=dict(size=10),
                        align="left"
                    ),
                    cells=dict(
                        values=details,
                        align="left")
                ),
                row=i + 3, col=1,
            )

        # Generate Map Labels
        fig.add_trace(
            go.Scattermapbox(
                lon=self.location_lons,
                lat=self.location_lats,
                mode='markers',
                marker=go.scattermapbox.Marker(
                    size=9
                ),
                text=self.location_labels,
                name="Locations",

            ),
            row=1, col=1
        )

        # Generate Overall Summary Table
        fig.add_trace(
            go.Table(
                header=dict(
                    values=["Driver", "Trips", "Time", "Earliest Pickup", "Latest Dropoff", "Miles", "Revenue"],
                    font=dict(size=10),
                    align="left"
                ),
                cells=dict(
                    values=[self.driver_names, self.trips, list(map(timedelta_to_hhmmss, self.times)),
                            list(map(timedelta_to_hhmmss, self.earliest_picks)),
                            list(map(timedelta_to_hhmmss, self.latest_drops)), self.miles, self.revenues],
                    align="left")
            ),
            row=2, col=1,
        )

        # Center Map and Add Legend
        fig.update_mapboxes(
            zoom=10,
            center=go.layout.mapbox.Center(
                lat=np.mean(all_lat),
                lon=np.mean(all_lon)),
            style='open-street-map')
        fig.update_layout(
            title_text=self.name,
            showlegend=True,
            height=(600 + 400 * (len(self.driver_names) + 1))
        )

        # Save to File
        fig.write_html(visualization_file_name, auto_open=open_in_browser)


def _get_coords_and_trip_data_from_df_filtered_by_driver(filtered_trips: DataFrame,
                                                         driver_id: int, driver_address: str) -> (
        Tuple[Tuple[float, float]], Tuple[Series]):
    """
    Get a sorted tuple of coordinates visited by each driver and a tuple of Pandas Series that contain bare bones trip information
    such as pickup_time, pickup_address, and driver id.
    :param filtered_trips: Pandas DataFrame containing trips associated with only a signle driver
    :param driver_id: The ID of the driver with which these trips are associated
    :param driver_address: The starting/ending address of the driver that these trips are associated with
    :return: A sorted tuple of coordinates visited and a sorted tuple of Pandas Series' containing trip starting information
    """
    pairs = []
    pairs.append((0.0, find_coord_lon_lat(driver_address), Series({})))
    for idx, t in filtered_trips.iterrows():
        pairs.append((float(t['est_pickup_time']), find_coord_lon_lat(t['trip_pickup_address']), t))
        pairs.append((float(t['est_dropoff_time']), find_coord_lon_lat(t['trip_dropoff_address']), Series(
            {'est_pickup_time': t['est_dropoff_time'], 'driver_id': driver_id, 'trip_id': 'INTER',
             'trip_pickup_address': t['trip_dropoff_address']})))

    pairs.append((1.0, find_coord_lon_lat(driver_address), Series({})))
    _, coords, trips = zip(*sorted(pairs, key=lambda x: x[0]))
    return coords, trips


def _get_driver_trips_times_miles_rev_from_df(sol_df: DataFrame, id: int) -> (
        str, str, float, float, float, float, float):
    """
    Generate a summary of the driver's overall day from the Solution Dataframe
    :param sol_df: DataFrame with the solution of the model containing the original trip details as well estimated pickups,
                    estimated dropoffs, and driver assigned to the trip
    :param id: ID of driver whose summary is to be generated
    :return: Driver Name, CSV of trip IDs, time traveled in the day, time of earliest pickup, time of latest dropoff,
            total miles traveled, total revenue earned
    """
    filtered_trips = sol_df[sol_df['driver_id'] == id]
    try:
        ep = (min(float(t['est_pickup_time']) for _, t in filtered_trips.iterrows()))
    except ValueError:
        ep = '0'
    try:
        ld = (max(float(t['est_dropoff_time']) for _, t in filtered_trips.iterrows()))
    except:
        ld = '0'
    name = ("".join(str(t['driver_name']) for _, t in filtered_trips.sample(1).iterrows())) + ";" + str(id)
    trps = ", ".join(t['trip_id'] for _, t in filtered_trips.iterrows())
    time = (sum(float(t['est_time']) for _, t in filtered_trips.iterrows()))
    m = (sum(float(t['est_miles']) for _, t in filtered_trips.iterrows()))
    r = (sum(float(t['trip_rev']) for _, t in filtered_trips.iterrows()))
    return name, trps, time, ep, ld, m, r


def load_assignment_from_df(assignment_df: DataFrame, drivers: List[Driver], name: str) -> Assignment:
    """
    Generate Assignment object from the solution DataFrame produced by Optimizer
    :param assignment_df: DataFrame with the solution of the model containing the original trip details as well estimated pickups,
                         estimated dropoffs, and driver assigned to the trip
    :param drivers: List of drivers associated with solution
    :param name: name of model
    :return: Assignment Object with details filled in from dataframe
    """
    assignment_date = datetime.strptime(assignment_df['trip_date'].iloc[0], '%m-%d-%Y')
    assign = Assignment(assignment_date, name)
    locations = dict()
    addresses = dict()
    for i, d in enumerate(drivers):
        filtered_trips = assignment_df[assignment_df['driver_id'] == d.id]
        points, trips = _get_coords_and_trip_data_from_df_filtered_by_driver(filtered_trips, d.id,
                                                                             d.get_clean_address())
        x, y = zip(*points)
        da = DriverAssignment()
        da.date = assignment_date
        da.driver_id = d.id
        da.assignment_id = assign.id
        da.trip_ids = [str(t['trip_id']) for _, t in filtered_trips.iterrows()]
        da.trip_pu = [t['trip_pickup_address'] for _, t in filtered_trips.iterrows()]
        da.trip_do = [t['trip_dropoff_address'] for _, t in filtered_trips.iterrows()]
        da.trip_est_pu = [timedelta(days=float(t['est_pickup_time'])) for _, t in
                          filtered_trips.iterrows()]
        da.trip_sch_pu = [timedelta(days=float(t['trip_pickup_time'])) for _, t in
                          filtered_trips.iterrows()]
        da.trip_est_do = [timedelta(days=float(t['est_dropoff_time'])) for _, t in
                          filtered_trips.iterrows()]
        da.trip_sch_do = [timedelta(days=float(t['trip_dropoff_time'])) for _, t in
                          filtered_trips.iterrows()]
        da.trip_miles = [(t['est_miles']) for _, t in filtered_trips.iterrows()]
        da.trip_los = [str(t['trip_los']) for _, t in filtered_trips.iterrows()]
        da.trip_rev = [(t['trip_rev']) for _, t in filtered_trips.iterrows()]
        da.lats = list(y)
        da.lons = list(x)
        assign.driver_assignments.append(da)
        names, ids, time, ep, ld, miles, rev = _get_driver_trips_times_miles_rev_from_df(assignment_df, d.id)
        assign.driver_names.append(names)
        assign.driver_ids.append(d.id)
        assign.trips.append(ids)
        assign.times.append(timedelta(days=time))
        assign.earliest_picks.append(timedelta(days=ep))
        assign.latest_drops.append(timedelta(days=ld))
        assign.miles.append(miles)
        assign.revenues.append(rev)
        points = points[1:-1]
        trips = trips[1:-1]
        for idx, point in enumerate(points):
            if point in locations:
                locations[point].append(trips[idx])
                locations[point] = list(sorted(locations[point], key=lambda x: float(x['est_pickup_time'])))
            else:
                locations[point] = [trips[idx]]
            if point not in addresses:
                addresses[point] = trips[idx]['trip_pickup_address']

    lon, lat = map(list, zip(*locations.keys()))
    labels = [generate_html_label_for_addr(locations[k], addresses[k]) for k in locations.keys()]

    for d in drivers:
        lon.append(find_coord_lon_lat(d.get_clean_address())[0])
        lat.append(find_coord_lon_lat(d.get_clean_address())[1])
        labels.append(generate_html_label_for_driver_addr(d))

    assign.location_lats = lat
    assign.location_lons = lon
    assign.location_labels = labels
    return assign


def load_assignment_from_csv(assignment_csv: str, drivers: List[Driver], mdl_name: str) -> Assignment:
    """
    Generate Assignment Object from solution stored in CSV
    :param assignment_csv: Path to CSV solution
    :param drivers: list of drivers associated with solution
    :param mdl_name: model name
    :return: Assignment object with details filled in from CSV
    """
    sol_df = pd.read_csv(assignment_csv)
    return load_assignment_from_df(sol_df, drivers, mdl_name)


def generate_visualization_from_db(assignment_id: int, session: Session,
                                   visualization_file_name: str = 'visualized.html',
                                   open_in_browser: bool = False) -> None:
    """
    Generate visualization for assignment that is in the database
    :param assignment_id: ID of the assignment for which the visualization is generated
    :param session: SQLAlchemy database connection seession
    :param visualization_file_name: path where the visualization will be stored
    :param open_in_browser: Whether the visualization will be opened in a browser after visualization is generated
    """
    assignment = session.query(Assignment).get(assignment_id)
    assignment.generate_visualization(visualization_file_name, open_in_browser)


def generate_visualization_from_df(sol_df: DataFrame, drivers: List[Driver], mdl_name: str,
                                   visualization_file_name: str = 'visualized.html',
                                   open_in_browser: bool = False) -> None:
    """
    Generate visualization from the solution dataframe produced by the optimizer
    :param sol_df: DataFrame with the solution of the model containing the original trip details as well estimated pickups,
                     estimated dropoffs, and driver assigned to the trip
    :param drivers: List of Drivers for which the solution was produced
    :param mdl_name: Name of Model
    :param visualization_file_name: path where visualization will be stored
    :param open_in_browser: Whether the visualization will be opened in browser after visualization is generated
    """
    load_assignment_from_df(sol_df, drivers, mdl_name).generate_visualization(visualization_file_name, open_in_browser)


def generate_visualization_from_csv(assignment_csv: str, drivers: List[Driver], mdl_name: str,
                                    visualization_file_name: str = 'visualized.html',
                                    open_in_browser: bool = False) -> None:
    """
    Generate visualization from a solution stored in CSV format
    :param assignment_csv: CSV file that can be loaded into a data frame of the same format as the Solution Dataframe
    :param drivers: List of Drivers for which the solution was produced
    :param mdl_name: Name of Model
    :param visualization_file_name: path where visualization will be stored
    :param open_in_browser: Whether the visualization will be opened in browser after visualization is generated
    """
    load_assignment_from_csv(assignment_csv, drivers, mdl_name).generate_visualization(visualization_file_name,
                                                                                       open_in_browser)

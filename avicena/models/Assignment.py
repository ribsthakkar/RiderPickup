from sqlalchemy import Column, Integer, DateTime, String, Interval, Float
from sqlalchemy.dialects.postgresql import ARRAY as Array
from sqlalchemy.orm import relationship

from .Database import Base

class Assignment(Base):
    __tablename__ = "assignment"
    id = Column(Integer, primary_key=True)
    date = Column(DateTime)
    name = Column(String)
    driver_assignments = relationship('DriverAssignment', backref='assignment')
    drivers = Column(Array(String))
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

    def serialize(self):
        return {"id": self.id,
                "date": self.date,
                "name": self.name}

    def save_to_db(self, session):
        session.add(self)
        session.commit()
        return self

    def generate_visualization(self):
        pass

def generate_visualization_from_csv():
    pass

def generate_visualization_from_db():
    pass

def visualize(sfile, drivers, mdl_name, vfile='visualized.html', open_after=False):
    def names(id):
        return "Driver " + str(id) + " Route"
    def get_labels(trips, addr):
        data = "<br>".join(
           "0" * (10 - len(str(t['trip_id']))) + str(t['trip_id']) + "  |  " + str(timedelta(days=float(t['est_pickup_time']))).split('.')[0] +
            "  |  " + str(t['driver_id']) for t in trips
        )
        return addr + "<br><b>TripID,             Time,      DriverID </b><br>" + data

    sol_df = pd.read_csv(sfile)
    driver_ids = list(d.id for d in drivers)
    titles = [names(i) for i in driver_ids]
    titles.insert(0, "Map")
    titles.insert(1, "Driver Summary: " + mdl_name)
    subplots = [[{"type": "table"}]] * (len(drivers) + 1)
    subplots.insert(0, [{"type": "scattermapbox"}])
    map_height = 600 / (600 + 2000 + 400 * (len(drivers)))
    summary_height = 600 / (600 + 2000 + 400 * (len(drivers)))
    heights = [(1 - map_height - summary_height - 0.12) / ((len(drivers)))] * (len(drivers))
    heights.insert(0, map_height)
    heights.insert(1, summary_height)
    fig = make_subplots(
        rows=2 + len(drivers), cols=1,
        vertical_spacing=0.015,
        subplot_titles=titles,
        specs=subplots,
        row_heights=heights
    )
    all_x = []
    all_y = []
    locations = dict()
    addresses = dict()
    for i, d in enumerate(drivers):
        r = lambda: random.randint(0, 255)
        col = '#%02X%02X%02X' % (r(), r(), r())
        filtered_trips = sol_df[sol_df['driver_id']==d.id]
        points, trips = _get_driver_coords(filtered_trips, d)
        x, y = zip(*points)
        details = [[str(t['trip_id']) for _, t in filtered_trips.iterrows()],
                   [t['trip_pickup_address'] for _,t in filtered_trips.iterrows()],
                   [t['trip_dropoff_address'] for _,t in filtered_trips.iterrows()],
                   [str(timedelta(days=float(t['est_pickup_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                   [str(timedelta(days=float(t['trip_pickup_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                   [str(timedelta(days=float(t['est_dropoff_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                   [str(timedelta(days=float(t['trip_dropoff_time']))).split('.')[0] for _,t in filtered_trips.iterrows()],
                   [str(t['est_miles']) for _,t in filtered_trips.iterrows()],
                   [str(t['trip_los']) for _,t in filtered_trips.iterrows()],
                   [str(t['trip_rev']) for _,t in filtered_trips.iterrows()],
                   ]
        all_x += x
        all_y += y
        fig.add_trace(go.Scattermapbox(
            lon=x,
            lat=y,
            mode='lines',
            marker=dict(
                size=8,
                color=col,
            ),
            name=names(d.id),

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
    labels = [get_labels(locations[k], addresses[k]) for k in locations.keys()]
    for d in drivers:
        lon.append(Location(d.address[:-4]).coord[1])
        lat.append(Location(d.address[:-4]).coord[0])
        labels.append(d.address[:-4] + "<br>Driver " + str(d.id) + " Home")
    fig.add_trace(
        go.Scattermapbox(
            lon=lon,
            lat=lat,
            mode='markers',
            marker=go.scattermapbox.Marker(
                size=9
            ),
            text=labels,
            name="Locations",

        ),
        row=1, col=1
    )
    names, ids, times, ep, ld,  miles, rev = zip(*(_get_driver_trips_times_miles_rev(sol_df, id) for id in driver_ids))
    names = list(names)
    ids = list(ids)
    times = list(times)
    ep = list(ep)
    ld = list(ld)
    miles = list(miles)
    rev = list(rev)
    ids.append("Average")
    times.append(sum(times)/len(times))
    ep.append(sum(ep)/len(ep))
    ld.append(sum(ld)/len(ld))
    miles.append(sum(miles)/len(miles))
    rev.append(sum(rev)/len(rev))
    times = list(map(lambda t: str(timedelta(days=t)).split('.')[0],times))
    ep = list(map(lambda t: str(timedelta(days=t)).split('.')[0],ep))
    ld = list(map(lambda t: str(timedelta(days=t)).split('.')[0],ld))
    miles = list(map(str, miles))
    rev = list(map(str, rev))
    fig.add_trace(
        go.Table(
            header=dict(
                values=["Driver", "Trips", "Time", "Earliest Pickup", "Latest Dropoff", "Miles", "Revenue"],
                font=dict(size=10),
                align="left"
            ),
            cells=dict(
                values=[names, ids, times, ep, ld, miles, rev],
                align="left")
        ),
        row=2, col=1,
    )
    fig.update_mapboxes(zoom=10,center=go.layout.mapbox.Center(
            lat=np.mean(all_y),
            lon=np.mean(all_x)),
     style='open-street-map')

    fig.update_layout(
        title_text=mdl_name,
        showlegend=True,
        height=(600 + 400 * (len(drivers) + 1))
    )
    fig.write_html(vfile, auto_open=open_after)

def _get_driver_coords(filtered_trips, driver):
    pairs = []
    pairs.append((0.0, Location(driver.address[:-4]).rev_coord(), {}))
    for idx, t in filtered_trips.iterrows():
        pairs.append((float(t['est_pickup_time']), Location(t['trip_pickup_address']).rev_coord(), t))
        pairs.append((float(t['est_dropoff_time']), Location(t['trip_dropoff_address']).rev_coord(), {'est_pickup_time': t['est_dropoff_time'], 'driver_id': driver.id, 'trip_id': 'INTER', 'trip_pickup_address': t['trip_dropoff_address']}))

    pairs.append((1.0, Location(driver.address[:-4]).rev_coord(), {}))
    _, coords, trips = zip(*sorted(pairs, key=lambda x: x[0]))
    return coords, trips

def _get_driver_trips_times_miles_rev(sol_df, id):
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

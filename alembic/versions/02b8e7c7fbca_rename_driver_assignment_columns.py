"""Rename driver assignment columns

Revision ID: 02b8e7c7fbca
Revises: 69859f4d0367
Create Date: 2020-08-18 23:17:43.161501

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '02b8e7c7fbca'
down_revision = '69859f4d0367'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('driver_assignment', sa.Column('trip_dropoff_addresses', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_estimated_dropoff_times', postgresql.ARRAY(sa.Interval()), nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_estimated_pickup_times', postgresql.ARRAY(sa.Interval()), nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_pickup_addresses', postgresql.ARRAY(sa.String()), nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_scheduled_dropoff_times', postgresql.ARRAY(sa.Interval()), nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_scheduled_pickup_times', postgresql.ARRAY(sa.Interval()), nullable=True))
    op.drop_column('driver_assignment', 'trip_est_pu')
    op.drop_column('driver_assignment', 'trip_sch_pu')
    op.drop_column('driver_assignment', 'trip_do')
    op.drop_column('driver_assignment', 'trip_pu')
    op.drop_column('driver_assignment', 'trip_sch_do')
    op.drop_column('driver_assignment', 'trip_est_do')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('driver_assignment', sa.Column('trip_est_do', postgresql.ARRAY(postgresql.INTERVAL()), autoincrement=False, nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_sch_do', postgresql.ARRAY(postgresql.INTERVAL()), autoincrement=False, nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_pu', postgresql.ARRAY(sa.VARCHAR()), autoincrement=False, nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_do', postgresql.ARRAY(sa.VARCHAR()), autoincrement=False, nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_sch_pu', postgresql.ARRAY(postgresql.INTERVAL()), autoincrement=False, nullable=True))
    op.add_column('driver_assignment', sa.Column('trip_est_pu', postgresql.ARRAY(postgresql.INTERVAL()), autoincrement=False, nullable=True))
    op.drop_column('driver_assignment', 'trip_scheduled_pickup_times')
    op.drop_column('driver_assignment', 'trip_scheduled_dropoff_times')
    op.drop_column('driver_assignment', 'trip_pickup_addresses')
    op.drop_column('driver_assignment', 'trip_estimated_pickup_times')
    op.drop_column('driver_assignment', 'trip_estimated_dropoff_times')
    op.drop_column('driver_assignment', 'trip_dropoff_addresses')
    # ### end Alembic commands ###

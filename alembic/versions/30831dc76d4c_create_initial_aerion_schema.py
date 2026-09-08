"""create_initial_aerion_schema

Revision ID: 30831dc76d4c
Revises: 
Create Date: 2026-09-08 23:48:09.622276

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '30831dc76d4c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Enable PostGIS extension
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # 2. organizations
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_organizations_slug', 'organizations', ['slug'], unique=True)

    # 3. users
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='operator'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_organization_id', 'users', ['organization_id'])
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 4. projects
    op.create_table(
        'projects',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('mode', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_projects_organization_id', 'projects', ['organization_id'])

    # 5. subscriptions
    op.create_table(
        'subscriptions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('plan', sa.String(length=50), nullable=False, server_default='FREE'),
        sa.Column('price_inr', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('current_period_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('current_period_end', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_subscriptions_organization_id', 'subscriptions', ['organization_id'], unique=True)

    # 6. assets
    op.create_table(
        'assets',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('storage_key', sa.String(length=1024), nullable=False),
        sa.Column('asset_type', sa.String(length=50), nullable=False),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('file_size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_assets_project_id', 'assets', ['project_id'])
    op.create_index('ix_assets_sha256', 'assets', ['sha256'])

    # 7. geofences
    op.create_table(
        'geofences',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('pixel_polygon', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('geom_polygon_4326', geoalchemy2.Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True), nullable=True),
        sa.Column('is_georeferenced', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('dwell_threshold', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_geofences_project_id', 'geofences', ['project_id'])

    # 8. analysis_jobs
    op.create_table(
        'analysis_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mode', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='queued'),
        sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_analysis_jobs_project_id', 'analysis_jobs', ['project_id'])
    op.create_index('ix_analysis_jobs_status', 'analysis_jobs', ['status'])

    # 9. analysis_results
    op.create_table(
        'analysis_results',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analysis_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('overall_status', sa.String(length=100), nullable=False),
        sa.Column('summary_critical', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary_high', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary_medium', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('summary_low', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('raw_payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_analysis_results_job_id', 'analysis_results', ['job_id'], unique=True)
    op.create_index('ix_analysis_results_analysis_id', 'analysis_results', ['analysis_id'], unique=True)

    # 10. detections
    op.create_table(
        'detections',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('class_name', sa.String(length=100), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('pixel_bbox_x1', sa.Float(), nullable=True),
        sa.Column('pixel_bbox_y1', sa.Float(), nullable=True),
        sa.Column('pixel_bbox_x2', sa.Float(), nullable=True),
        sa.Column('pixel_bbox_y2', sa.Float(), nullable=True),
        sa.Column('pixel_obb_points', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('geom_point_4326', geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=True),
        sa.Column('is_georeferenced', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('track_id', sa.Integer(), nullable=True),
        sa.Column('frame_number', sa.Integer(), nullable=True),
    )
    op.create_index('ix_detections_result_id', 'detections', ['result_id'])

    # 11. tracks
    op.create_table(
        'tracks',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('class_name', sa.String(length=100), nullable=True),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('pixel_center_x', sa.Float(), nullable=False),
        sa.Column('pixel_center_y', sa.Float(), nullable=False),
        sa.Column('pixel_trajectory', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('geom_point_4326', geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=True),
        sa.Column('geom_trajectory_4326', geoalchemy2.Geometry(geometry_type='LINESTRING', srid=4326, spatial_index=True), nullable=True),
        sa.Column('is_georeferenced', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('direction', sa.String(length=50), nullable=True),
        sa.Column('persistence', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('frame_number', sa.Integer(), nullable=False),
    )
    op.create_index('ix_tracks_result_id', 'tracks', ['result_id'])
    op.create_index('ix_tracks_track_id', 'tracks', ['track_id'])

    # 12. border_events
    op.create_table(
        'border_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('geofence_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('geofences.id', ondelete='SET NULL'), nullable=True),
        sa.Column('track_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('alert_level', sa.String(length=50), nullable=False),
        sa.Column('border_score', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('pixel_location_x', sa.Float(), nullable=False),
        sa.Column('pixel_location_y', sa.Float(), nullable=False),
        sa.Column('geom_point_4326', geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=True),
        sa.Column('is_georeferenced', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('frame_number', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_border_events_result_id', 'border_events', ['result_id'])

    # 13. damage_analyses
    op.create_table(
        'damage_analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('threshold', sa.Numeric(precision=5, scale=4), nullable=False, server_default='0.50'),
        sa.Column('damage_pixels', sa.BigInteger(), nullable=False),
        sa.Column('total_pixels', sa.BigInteger(), nullable=False),
        sa.Column('damage_ratio', sa.Numeric(precision=7, scale=6), nullable=False),
        sa.Column('damage_percentage', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('probability_mean', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('mask_storage_key', sa.String(length=1024), nullable=True),
    )
    op.create_index('ix_damage_analyses_result_id', 'damage_analyses', ['result_id'], unique=True)

    # 14. usage_events
    op.create_table(
        'usage_events',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('dimension', sa.String(length=50), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_jobs.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_usage_events_organization_id', 'usage_events', ['organization_id'])
    op.create_index('ix_usage_events_created_at', 'usage_events', ['created_at'])

    # 15. evidence_records
    op.create_table(
        'evidence_records',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_evidence_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False, server_default='{}'),
        sa.Column('source_type', sa.String(length=100), nullable=False),
        sa.Column('temporal_mode', sa.String(length=50), nullable=False),
        sa.Column('asset_timestamp_utc', sa.DateTime(timezone=True), nullable=True),
        sa.Column('modality', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('verification_state', sa.String(length=50), nullable=False),
        sa.Column('pixel_bbox', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('geom_point_4326', geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=True),
        sa.Column('geom_polygon_4326', geoalchemy2.Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True), nullable=True),
        sa.Column('sensor_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('raw_payload_uri', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_evidence_records_project_id', 'evidence_records', ['project_id'])

    # 16. situations
    op.create_table(
        'situations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('mode', sa.String(length=50), nullable=False),
        sa.Column('temporal_mode', sa.String(length=50), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('overall_threat_level', sa.String(length=50), nullable=False),
        sa.Column('overall_score', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('active_frame_index', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_situations_project_id', 'situations', ['project_id'])
    op.create_index('ix_situations_session_id', 'situations', ['session_id'])

    # 17. situation_events
    op.create_table(
        'situation_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('situation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('situations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('sequence_number', sa.BigInteger(), nullable=False),
        sa.Column('event_timestamp_utc', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('threat_level', sa.String(length=50), nullable=False),
        sa.Column('evidence_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('geom_point_4326', geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=True),
        sa.Column('sector_id', sa.String(length=100), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_situation_events_situation_id', 'situation_events', ['situation_id'])
    op.create_index('idx_situation_events_seq', 'situation_events', ['situation_id', 'sequence_number'])

    # 18. situation_reports
    op.create_table(
        'situation_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('situation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('situations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('operation_mode', sa.String(length=50), nullable=False),
        sa.Column('temporal_mode', sa.String(length=50), nullable=False),
        sa.Column('report_json', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('overall_confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('mistral_advisory_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_situation_reports_situation_id', 'situation_reports', ['situation_id'])

    # 19. shelters
    op.create_table(
        'shelters',
        sa.Column('id', sa.String(length=100), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('geom_point_4326', geoalchemy2.Geometry(geometry_type='POINT', srid=4326, spatial_index=True), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('capacity_total', sa.Integer(), nullable=False),
        sa.Column('capacity_occupied', sa.Integer(), nullable=False),
        sa.Column('is_generator_powered', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('medical_support_available', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('source_registry', sa.String(length=255), nullable=False),
        sa.Column('last_reported_utc', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_shelters_project_id', 'shelters', ['project_id'])

    # 20. hazard_zones
    op.create_table(
        'hazard_zones',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('hazard_type', sa.String(length=100), nullable=False),
        sa.Column('threat_level', sa.String(length=50), nullable=False),
        sa.Column('geom_polygon_4326', geoalchemy2.Geometry(geometry_type='POLYGON', srid=4326, spatial_index=True), nullable=False),
        sa.Column('evidence_ids', postgresql.ARRAY(postgresql.UUID(as_uuid=True)), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('identified_at_utc', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_hazard_zones_project_id', 'hazard_zones', ['project_id'])

    # 21. intelligence_items
    op.create_table(
        'intelligence_items',
        sa.Column('id', sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column('result_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_results.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('priority', sa.String(length=20), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=5, scale=4), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('item_metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='{}'),
    )
    op.create_index('ix_intelligence_items_result_id', 'intelligence_items', ['result_id'])


def downgrade() -> None:
    op.drop_table('intelligence_items')
    op.drop_table('hazard_zones')
    op.drop_table('shelters')
    op.drop_table('situation_reports')
    op.drop_table('situation_events')
    op.drop_table('situations')
    op.drop_table('evidence_records')
    op.drop_table('usage_events')
    op.drop_table('damage_analyses')
    op.drop_table('border_events')
    op.drop_table('tracks')
    op.drop_table('detections')
    op.drop_table('analysis_results')
    op.drop_table('analysis_jobs')
    op.drop_table('geofences')
    op.drop_table('assets')
    op.drop_table('subscriptions')
    op.drop_table('projects')
    op.drop_table('users')
    op.drop_table('organizations')

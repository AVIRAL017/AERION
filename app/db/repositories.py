"""
AERION — Database Repositories
Clean repository boundary isolating business logic from direct SQLAlchemy queries.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Organization,
    User,
    Project,
    Asset,
    Geofence,
    AnalysisJob,
    AnalysisResult,
    Detection,
    DamageAnalysis,
    EvidenceRecord,
    Situation,
    SituationEvent,
    SituationReport,
    Shelter,
    HazardZone,
    Subscription,
    UsageEvent,
)

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Base generic repository for CRUD operations."""
    def __init__(self, session: AsyncSession, model: Type[T]):
        self.session = session
        self.model = model

    async def get_by_id(self, item_id: Any) -> Optional[T]:
        return await self.session.get(self.model, item_id)

    async def list_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, instance: T) -> T:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: T) -> None:
        await self.session.delete(instance)
        await self.session.flush()


class OrganizationRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Organization)

    async def get_by_slug(self, slug: str) -> Optional[Organization]:
        stmt = select(Organization).where(Organization.slug == slug)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class UserRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class ProjectRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Project)

    async def list_by_organization(self, organization_id: uuid.UUID) -> List[Project]:
        stmt = select(Project).where(Project.organization_id == organization_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class AnalysisJobRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AnalysisJob)

    async def update_status(
        self,
        job_id: uuid.UUID,
        status: str,
        progress_percent: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> Optional[AnalysisJob]:
        job = await self.get_by_id(job_id)
        if job:
            job.status = status
            if progress_percent is not None:
                job.progress_percent = progress_percent
            if error_message is not None:
                job.error_message = error_message
            await self.session.flush()
        return job


class EvidenceRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, EvidenceRecord)

    async def list_by_project(self, project_id: uuid.UUID) -> List[EvidenceRecord]:
        stmt = select(EvidenceRecord).where(EvidenceRecord.project_id == project_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class SituationRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Situation)

    async def get_active_by_project(self, project_id: uuid.UUID) -> Optional[Situation]:
        stmt = select(Situation).where(
            Situation.project_id == project_id,
            Situation.is_active == True,
        )
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class AnalysisResultRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, AnalysisResult)

    async def get_by_analysis_id(self, analysis_id: uuid.UUID) -> Optional[AnalysisResult]:
        stmt = select(AnalysisResult).where(AnalysisResult.analysis_id == analysis_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class DetectionRepository(BaseRepository[Detection]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, Detection)

    async def list_by_result_id(self, result_id: uuid.UUID) -> List[Detection]:
        stmt = select(Detection).where(Detection.result_id == result_id)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())


class DamageAnalysisRepository(BaseRepository[DamageAnalysis]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, DamageAnalysis)

    async def get_by_result_id(self, result_id: uuid.UUID) -> Optional[DamageAnalysis]:
        stmt = select(DamageAnalysis).where(DamageAnalysis.result_id == result_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()


class SituationEventRepository(BaseRepository):
    def __init__(self, session: AsyncSession):
        super().__init__(session, SituationEvent)

    async def list_by_situation(self, situation_id: uuid.UUID) -> List[SituationEvent]:
        stmt = select(SituationEvent).where(SituationEvent.situation_id == situation_id).order_by(SituationEvent.sequence_number.asc())
        res = await self.session.execute(stmt)
        return list(res.scalars().all())

"""Week 02 data model: reference seed + new-table CRUD (spec Ch 9.3)."""
from app.db import SessionLocal
from app.models import (
    DEFAULT_ORG_ID,
    AuditLog,
    BaseGlazing,
    Organization,
    ZipLookupCache,
)


def test_reference_data_seeded(client):
    s = SessionLocal()
    try:
        assert s.get(Organization, DEFAULT_ORG_ID) is not None
        # 8 common assemblies (Week 04 base-glass catalog).
        assert s.query(BaseGlazing).count() >= 8
        assert s.get(BaseGlazing, "triple_clear_lowE_argon") is not None
    finally:
        s.close()


def test_new_tables_crud(client):
    s = SessionLocal()
    try:
        s.add(ZipLookupCache(zip="33540", kind="solar", payload={"ghi": 1700}))
        s.add(AuditLog(action="project.create", target_table="projects", target_id="x"))
        s.commit()
        assert s.query(ZipLookupCache).filter_by(zip="33540", kind="solar").count() == 1
        assert s.query(AuditLog).filter_by(action="project.create").count() == 1
    finally:
        s.close()

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import models as m
from app.db.base import get_db

DbDep = Depends(get_db)


def get_application_or_404(application_id: str, db: Session) -> m.Application:
    app = db.get(m.Application, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail=f"Application {application_id} not found")
    return app

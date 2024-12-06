from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text as sa_text
from app.models import db
from app.models.model_mixin import ModelMixin
import uuid

class UserExperiments(ModelMixin):
    __tablename__ = 'user_experiments'

    id = db.Column(UUID(as_uuid=True), primary_key=True,default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True))
    experiment_id =  db.Column(db.String)
    app_id = db.Column(UUID(as_uuid=True))
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())

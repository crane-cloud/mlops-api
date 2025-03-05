from marshmallow import Schema, fields, EXCLUDE, validate


class ProjectSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    id = fields.Str(required=True)
    alias = fields.Str(required=True)


class ClusterSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    id = fields.Str(required=True)
    host = fields.Str(required=True)
    token = fields.Str(required=True)
    sub_domain = fields.Str(required=True)


class AppDeploySchema(Schema):
    class Meta:
        unknown = EXCLUDE

    name = fields.Str(required=True)
    is_notebook = fields.Bool(required=True)
    image = fields.Str(required=False)
    project = fields.Nested(ProjectSchema, required=True, unknown=EXCLUDE)
    cluster = fields.Nested(ClusterSchema, required=True, unknown=EXCLUDE)
    is_modal = fields.Bool(required=False)
    model_image_uri = fields.Str(required=False)
    api_type = fields.Str(required=False, default="REST", validate=validate.OneOf(
        ["REST", "GRPC"]
    ))
    model_server = fields.Str(required=False, default="MLFLOW_SERVER", validate=validate.OneOf(
        [
            "SKLEARN_SERVER",
            "TENSORFLOW_SERVER",
            "XGBOOST_SERVER",
            "MLFLOW_SERVER",
            "TRITON_SERVER",
            "TEMPO_SERVER",
            "HUGGINGFACE_SERVER",
            "CUSTOM_INFERENCE_SERVER"
        ]
    ))

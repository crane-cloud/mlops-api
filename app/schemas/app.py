from marshmallow import Schema, fields, EXCLUDE


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

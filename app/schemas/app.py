from marshmallow import Schema, fields


class ProjectSchema(Schema):
    id = fields.Str(required=True)
    alias = fields.Str(required=True)


class ClusterSchema(Schema):
    id = fields.Str(required=True)
    host = fields.Str(required=True)
    token = fields.Str(required=True)
    sub_domain = fields.Str(required=True)


class AppDeploySchema(Schema):
    name = fields.Str(required=True)
    project = fields.Nested(ProjectSchema, required=True)
    cluster = fields.Nested(ClusterSchema, required=True)

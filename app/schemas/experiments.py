from marshmallow import Schema, fields, EXCLUDE


class ExperimentsSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    name = fields.Str(required=False)
    tags = fields.Str(required=False)


class UserExperimentsSchema(Schema):

    id = fields.UUID(dump_only=True)  
    user_id = fields.UUID() 
    experiment_id = fields.String(required=True) 
    app_id = fields.UUID(required=True) 
    created_at = fields.DateTime(required=True)   
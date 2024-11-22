from marshmallow import Schema, fields, EXCLUDE


class ExperimentsSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    name = fields.Str(required=False)
    tags = fields.Str(required=False)




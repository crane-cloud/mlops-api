from marshmallow import Schema, fields, EXCLUDE


class RunsSchema(Schema):
    class Meta:
        unknown = EXCLUDE
    run_name = fields.Str(required=True)
    status = fields.Str(required=False)




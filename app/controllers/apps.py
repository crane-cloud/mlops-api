from flask_restful import Resource
from app.helpers.authenticate import (
    jwt_required
)


class AppsView(Resource):
    @jwt_required
    def post(self):
        return dict(status="success", message="Welcome to Crane Cloud MLOps API")

    @jwt_required
    def get(self, current_user):
        print(current_user)
        return dict(status="success", message="Welcome to Crane Cloud MLOps API")

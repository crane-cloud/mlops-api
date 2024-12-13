from app.helpers.authenticate import jwt_required
from app.helpers.mlflow_service import get_mlflow_experiments, get_mlflow_client, get_experiment_json_object
from flask_restful import Resource, request
from app.schemas.experiments import ExperimentsSchema
from app.models.user_experiments import UserExperiments
import marshmallow
from types import SimpleNamespace
import json


class ExperimentView(Resource):

    @jwt_required
    def get(self, current_user):
       
        mlflow_client = get_mlflow_client()  # Initialize the MLflow client
        app_alias = request.args.get('app_alias') 
        user_id = request.args.get('user_id')

        if not user_id and not app_alias:
            return {"error": "At least one of 'userID' or 'appAlias' must be provided"}, 400
        
        try:
            filter_string = ""
            if user_id:
                filter_string = f"tags.user_tag = '{user_id}'"
            if app_alias:
                if filter_string:
                    filter_string += f" AND tags.app_tag = '{app_alias}'"
                else:
                    filter_string = f"tags.app_tag = '{app_alias}'"

            print(filter_string)
        
            experiments = mlflow_client.search_experiments(filter_string=filter_string)

            print(experiments)

            if not experiments:
                return { "status": "success", "message": "No experiments found for the provided criteria"}, 404
            
            response = list(map(get_experiment_json_object, experiments))

            return {"status": "success", "data": response}, 200
        
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500


class ExperimentDetailView(Resource):

    @jwt_required
    def get(self, experiment_id, current_user):
        """ Retrieve a single experiment by ID """
        try:
            experiment = get_mlflow_client().get_experiment(experiment_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 404

        return {"status": "success",
                "data": get_experiment_json_object(experiment)}

    @jwt_required
    def patch(self, experiment_id, current_user):
        """ Update experiment details """
        experiments_schema = ExperimentsSchema()
        try:
            validated_data = experiments_schema.load(request.json)
        except marshmallow.exceptions.ValidationError as e:
            return dict(status="error", message=e.messages), 400

        experiment_data = SimpleNamespace(**validated_data)

        try:
            if experiment_data.name:
                get_mlflow_client().rename_experiment(
                    experiment_id, experiment_data.name)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

        return {"status": "success", "message": "Experiment updated successfully"}

    @jwt_required
    def delete(self, experiment_id, current_user):
        """ Delete an experiment """
        try:
            get_mlflow_client().delete_experiment(experiment_id)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 400

        return {"status": "success", "message": "Experiment deleted successfully"}

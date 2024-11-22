from app.helpers.authenticate import jwt_required
from app.helpers.mlflow_service import get_mlflow_experiments, get_mlflow_client, get_experiment_json_object
from flask_restful import Resource, request
from app.schemas.experiments import ExperimentsSchema
import marshmallow
from types import SimpleNamespace


class ExperimentView(Resource):

    @jwt_required
    def get(self, current_user):
        """
        Retrieve all experiments
        """
        mlflow_client = get_mlflow_client()
        name = request.args.get('name', None)

        try:
            experiments = get_mlflow_experiments(mlflow_client, name)
        except Exception as e:
            return {"status": "error", "message": str(e)}, 500

        return {"status": "success",
                "data": [get_experiment_json_object(exp) for exp in experiments]}


class ExperimenDetailView(Resource):

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

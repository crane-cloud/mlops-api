from flask_restful import Api
from app.controllers import (
    IndexView, AppsView, ExperimentRunsView, ExperimentView, RunDetailView, ExperimentDetailView)

api = Api()

# Index route
api.add_resource(IndexView, '/')

# Apps route
api.add_resource(AppsView, '/apps')

api.add_resource(ExperimentView, '/experiments')
api.add_resource(ExperimentDetailView, '/experiments/<experiment_id>')
api.add_resource(ExperimentRunsView, '/experiments/<experiment_id>/runs')
api.add_resource(RunDetailView, '/run/<run_id>')

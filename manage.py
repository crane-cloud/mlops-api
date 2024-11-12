import click
from flask.cli import with_appcontext
from app.helpers.admin import create_superuser, create_default_roles


@click.command('admin_user',help='Create an admin user')
@click.option('-e', '--email', prompt=True, help='admin email')
@click.option('-p', '--password', prompt=True, help='admin password')
@click.option('-c', '--confirm_password', prompt=True, help='confirm_password')
@with_appcontext
def admin_user(email, password, confirm_password):
    create_superuser(email, password, confirm_password)


@click.command('create_roles', help='Create default user roles')
@with_appcontext
def create_roles():
    create_default_roles()

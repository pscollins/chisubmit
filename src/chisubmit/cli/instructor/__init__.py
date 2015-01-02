import click
from chisubmit.cli.instructor.assignment import instructor_assignment
from chisubmit.cli.instructor.team import instructor_team
from chisubmit.cli.instructor.user import instructor_user

@click.group()
@click.pass_context
def instructor(ctx):
    pass

instructor.add_command(instructor_assignment)
instructor.add_command(instructor_team)
instructor.add_command(instructor_user)
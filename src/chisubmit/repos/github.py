
# Needed so we can import from the global "github" package
from __future__ import absolute_import

from github import Github, InputGitAuthor
from github.GithubException import GithubException

from chisubmit.repos import RemoteRepositoryConnectionBase
from chisubmit.core import ChisubmitException
import pytz
from datetime import datetime

class GitHubConnection(RemoteRepositoryConnectionBase):

    def __init__(self, connection_string):
        RemoteRepositoryConnectionBase.__init__(self, connection_string)

        self.organization = None
        self.gh = None

    @staticmethod
    def get_server_type_name():
        return "GitHub"

    @staticmethod
    def get_connstr_mandatory_params():
        return ["github_organization"]

    @staticmethod
    def get_connstr_optional_params():
        return []


    @staticmethod
    def get_credentials(username, password, delete_repo = False):
        gh = Github(username, password)
        token = None

        try:
            u = gh.get_user()

            scopes = ['user', 'public_repo', 'repo', 'gist']
            note = "Created by chisubmit."

            if delete_repo:
                scopes.append("delete_repo")
                note += " Has delete permissions."

            auth = u.create_authorization(scopes = scopes, note = note)
            token = auth.token
        except GithubException as ge:
            if ge.status == 401:
                return None
            else:
                raise ChisubmitException("Unexpected error creating authorization token (%i: %s)" % (ge.status, ge.data["message"]), ge)

        return token


    def connect(self, credentials):
        # Credentials are a GitHub access token

        self.gh = Github(credentials)

        try:
            self.organization = self.gh.get_organization(self.github_organization)
        except GithubException as ge:
            if ge.status == 401:
                raise ChisubmitException("Invalid Github Credentials", ge)
            elif ge.status == 404:
                raise ChisubmitException("Organization %s does not exist" % self.github_organization, ge)
            else:
                raise ChisubmitException("Unexpected error accessing organization %s (%i: %s)" % (self.github_organization, ge.status, ge.data["message"]), ge)


    def init_course(self, course, fail_if_exists=True):
        instructors_ghteam = self.__create_ghteam(self.__get_instructors_ghteam_name(course), [], "admin", fail_if_exists = fail_if_exists)
        graders_ghteam = self.__create_ghteam(self.__get_graders_ghteam_name(course), [], "push", fail_if_exists = fail_if_exists)

        for instructor in course.instructors:
            self.__add_user_to_ghteam(instructor.git_server_id, instructors_ghteam)

        for grader in course.graders:
            self.__add_user_to_ghteam(grader.git_server_id, graders_ghteam)


    def update_instructors(self, course):
        instructors_ghteam = self.__get_ghteam_by_name(self.__get_instructors_ghteam_name(course))

        for instructor in course.instructors:
            self.__add_user_to_ghteam(instructor.git_server_id, instructors_ghteam)

        # TODO: Remove instructors that may have been removed


    def update_graders(self, course):
        graders_ghteam = self.__get_ghteam_by_name(self.__get_graders_ghteam_name(course))

        for grader in course.graders:
            self.__add_user_to_ghteam(grader.git_server_id, graders_ghteam)

        # TODO: Remove graders that may have been removed


    def create_team_repository(self, course, team, team_access, fail_if_exists=True, private=True):
        repo_name = self.__get_team_ghrepo_name(course, team)
        student_names = ", ".join(["%s %s" % (s.first_name, s.last_name) for s in team.students])
        repo_description = "%s: Team %s (%s)" % (course.name, team.id, student_names)
        github_instructors = self.__get_ghteam_by_name(self.__get_instructors_ghteam_name(course))
        github_graders = self.__get_ghteam_by_name(self.__get_graders_ghteam_name(course))

        if team_access:
            github_students = []

            # Make sure users exist
            for s in team.students:
                github_student = self.__get_user(s.git_server_id)

                if github_student is None:
                    raise ChisubmitException("GitHub user '%s' does not exist " % (s.git_server_id))

                github_students.append(github_student)

        github_repo = self.__get_repository(repo_name)

        if github_repo is None:
            try:
                github_repo = self.organization.create_repo(repo_name, description=repo_description, private=private)
            except GithubException as ge:
                raise ChisubmitException("Unexpected exception creating repository %s (%i: %s)" % (repo_name, ge.status, ge.data["message"]), ge)
        else:
            if fail_if_exists:
                raise ChisubmitException("Repository %s already exists" % repo_name)

        try:
            github_instructors.add_to_repos(github_repo)
        except GithubException as ge:
            raise ChisubmitException("Unexpected exception adding repository to Instructors team (%i: %s)" % (ge.status, ge.data["message"]), ge)

        try:
            github_graders.add_to_repos(github_repo)
        except GithubException as ge:
            raise ChisubmitException("Unexpected exception adding repository to Graders team (%i: %s)" % (ge.status, ge.data["message"]), ge)

        if team_access:
            team_name = self.__get_team_ghteam_name(course, team)

            github_team = self.__create_ghteam(team_name, [github_repo], "push", fail_if_exists)

            for github_student in github_students:
                try:
                    github_team.add_to_members(github_student)
                except GithubException as ge:
                    raise ChisubmitException("Unexpected exception adding user %s to team (%i: %s)" % (s.git_server_id, ge.status, ge.data["message"]), ge)


    def update_team_repository(self, course, team):
        github_team = self.__get_ghteam_by_name(self.__get_team_ghteam_name(course, team))

        for s in team.students:
            github_student = self.__get_user(s.git_server_id)
            try:
                github_team.add_to_members(github_student)
            except GithubException as ge:
                raise ChisubmitException("Unexpected exception adding user %s to team (%i: %s)" % (s.git_server_id, ge.status, ge.data["message"]))

        #TODO: Remove students that may have been removed from team

    def exists_team_repository(self, course, team):
        r = self.__get_repository(self.__get_team_ghrepo_name(course, team))

        return (r is not None)


    def get_repository_git_url(self, course, team):
        orgname = self.github_organization
        reponame = self.__get_team_ghrepo_name(course, team)
        return "git@github.com:%s/%s.git" % (orgname, reponame)

    def get_repository_http_url(self, course, team):
        orgname = self.github_organization
        reponame = self.__get_team_ghrepo_name(course, team)
        return "https://github.com/%s/%s" % (orgname, reponame)


    # Return new commit object
    def get_commit(self, course, team, commit_sha):
        try:
            github_repo = self.organization.get_repo(self.__get_team_ghrepo_name(course, team))
            commit = github_repo.get_commit(commit_sha)
            return commit
        except GithubException as ge:
            if ge.status == 404:
                return None
            else:
                raise ChisubmitException("Unexpected error when fetching commit %s (%i: %s)" % (commit_sha, ge.status, ge.data["message"]), ge)


    def create_submission_tag(self, course, team, tag_name, tag_message, commit_sha):
        github_repo = self.organization.get_repo(self.__get_team_ghrepo_name(course, team))

        commit = self.get_commit(course, team, commit_sha)

        this_user = self.gh.get_user()

        if this_user.name is None:
            user_name = "Team %s" % team.id
        else:
            user_name = this_user.name

        if this_user.email is None:
            user_email = "unspecified@example.org"
        else:
            user_email = this_user.email

        tz = pytz.timezone("America/Chicago")
        dt = tz.localize(datetime.now().replace(microsecond=0))
        iu = InputGitAuthor(user_name, user_email, dt.isoformat())

        tag = github_repo.create_git_tag(tag_name, tag_message, commit.sha, "commit", iu)
        ref = github_repo.create_git_ref("refs/tags/" + tag.tag, tag.sha)


    def update_submission_tag(self, course, team, tag_name, tag_message, commit_sha):
        submission_tag_ref = self.__get_submission_tag_ref(course, team, tag_name)
        submission_tag_ref.delete()

        self.create_submission_tag(team, tag_name, tag_message, commit_sha)


    # Return a new "tag" object
    def get_submission_tag(self, course, team, tag_name):
        github_repo = self.organization.get_repo(self.__get_team_ghrepo_name(course, team))

        submission_tag_ref = self.__get_submission_tag_ref(course, team, tag_name)

        if submission_tag_ref is None:
            return None

        submission_tag = github_repo.get_git_tag(submission_tag_ref.object.sha)

        return submission_tag


    def delete_team_repository(self, course, team):
        ghrepo_name = self.__get_team_ghrepo_name(course, team)
        try:
            github_repo = self.organization.get_repo(ghrepo_name)
        except GithubException as ge:
            raise ChisubmitException("Unexpected exception fetching repository %s (%i: %s)" % (ghrepo_name, ge.status, ge.data["message"]), ge)

        try:
            github_repo.delete()
        except GithubException as ge:
            raise ChisubmitException("Unexpected exception deleting repository %s (%i: %s)" % (ghrepo_name, ge.status, ge.data["message"]), ge)

        github_team_name = self.__get_team_ghteam_name(course, team)
        github_team = self.__get_ghteam_by_name(github_team_name)

        try:
            github_team.delete()
        except GithubException as ge:
            raise ChisubmitException("Unexpected exception deleting team %s (%i: %s)" % (github_team_name, ge.status, ge.data["message"]), ge)


    def __get_instructors_ghteam_name(self, course):
        return "%s-instructors" % course.id

    def __get_graders_ghteam_name(self, course):
        return "%s-graders" % course.id

    def __get_team_ghteam_name(self, course, team):
        return "%s-%s" % (course.id, team.id)

    def __get_team_ghrepo_name(self, course, team):
        return "%s-%s" % (course.id, team.id)

    def __create_ghteam(self, team_name, repos, permissions, fail_if_exists = True):
        github_team = self.__get_ghteam_by_name(team_name)

        if github_team is not None:
            if fail_if_exists:
                raise ChisubmitException("Team %s already exists." % team_name)
            else:
                return github_team
        else:
            try:
                github_team = self.organization.create_team(team_name, repos, permissions)
                return github_team
            except GithubException as ge:
                raise ChisubmitException("Unexpected exception creating team %s (%i: %s)" % (team_name, ge.status, ge.data["message"]), ge)

    def __add_user_to_ghteam(self, github_id, ghteam):
        github_user = self.__get_user(github_id)

        if github_user is None:
            raise ChisubmitException("GitHub user '%s' does not exist " % github_id)

        try:
            ghteam.add_to_members(github_user)
        except GithubException as ge:
            raise ChisubmitException("Unexpected exception adding user %s to team (%i: %s)" % (github_id, ge.status, ge.data["message"]), ge)

    def __add_user_to_ghteam_by_name(self, github_id, ghteam_name):
        ghteam = self.__get_ghteam_by_name(ghteam_name)

        if ghteam is None:
            raise ChisubmitException("GitHub team '%s' does not exist " % ghteam_name)

        self.__add_user_to_ghteam(github_id, ghteam)


    def __get_user(self, username):
        try:
            user = self.gh.get_user(username)
            return user
        except GithubException as ge:
            if ge.status == 404:
                return None
            else:
                raise ChisubmitException("Unexpected error with user %s (%i: %s)" % (username, ge.status, ge.data["message"]), ge)


    def __get_repository(self, repository_name):
        try:
            repository = self.organization.get_repo(repository_name)
            return repository
        except GithubException as ge:
            if ge.status == 404:
                return None
            else:
                raise ChisubmitException("Unexpected error with repository %s (%i: %s)" % (repository_name, ge.status, ge.data["message"]), ge)


    def __get_ghteam_by_name(self, team_name):
        try:
            teams = self.organization.get_teams()
            for t in teams:
                if t.name == team_name:
                    return t
            return None
        except GithubException as ge:
            raise ChisubmitException("Unexpected error with team %s (%i: %s)" % (team_name, ge.status, ge.data["message"]), ge)


    def __get_submission_tag_ref(self, course, team, tag_name):
        github_repo = self.organization.get_repo(self.__get_team_ghrepo_name(course, team))

        try:
            submission_tag_ref = github_repo.get_git_ref("tags/" + tag_name)
        except GithubException as ge:
            if ge.status == 404:
                return None
            else:
                raise ChisubmitException("Unexpected error when fetching tag %s (%i: %s)" % (tag_name, ge.status, ge.data["message"]), ge)

        return submission_tag_ref


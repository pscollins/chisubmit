import abc
from chisubmit.core import ChisubmitException

class ConnectionString(object):

    def __init__(self, s):
        params = s.split(";")
        params = [x.split("=") for x in params]

        try:
            params = dict([(k.strip(), v.strip()) for k,v in params])
        except ValueError, ve:
            raise ChisubmitException("Improperly formatted connection string: %s" % s, original_exception = ve)

        if not params.has_key("server_type"):
            raise ChisubmitException("Connection string does not have 'server_type' parameter: %s" % s)

        self.server_type = params.pop("server_type")
        self.params = params

    @abc.abstractmethod
    def to_string(self):
        pass


class RemoteRepositoryConnectionBase(object):

    def __init__(self, connection_string):
        if connection_string.server_type != self.get_server_type_name():
            raise ChisubmitException("Expected server_type in connection string to be '%s', got '%s'" %
                                     (self.get_server_type_name(), connection_string.server_type))

        param_names = connection_string.params.keys()

        for p in self.get_connstr_mandatory_params():
            if p not in param_names:
                raise ChisubmitException("Connection string does not have required parameter '%s'" % p)
            param_names.remove(p)
            setattr(self, p, connection_string.params[p])

        for p in param_names:
            if p not in self.get_connstr_optional_params():
                raise ChisubmitException("Connection string has invalid parameter '%s'" % p)
            setattr(self, p, connection_string.params[p])

        for p in self.get_connstr_optional_params():
            if p not in param_names:
                setattr(self, p, None)


        self.is_connected = False

    @staticmethod
    @abc.abstractmethod
    def get_server_type_name():
        pass

    @staticmethod
    @abc.abstractmethod
    def get_connstr_mandatory_params():
        pass

    @staticmethod
    @abc.abstractmethod
    def get_connstr_optional_params():
        pass


    @abc.abstractmethod
    def connect(self):
        pass

    @abc.abstractmethod
    def disconnect(self):
        pass

    @abc.abstractmethod
    def init_course(self, course, fail_if_exists=True):
        pass

    @abc.abstractmethod
    def update_instructors(self, course):
        pass

    @abc.abstractmethod
    def update_graders(self, course):
        pass

    @abc.abstractmethod
    def create_team_repository(self, course, team, team_access, fail_if_exists=True, private=True):
        pass

    @abc.abstractmethod
    def update_team_repository(self, course, team):
        pass

    @abc.abstractmethod
    def exists_team_repository(self, course, team):
        pass

    @abc.abstractmethod
    def get_repository_git_url(self, course, team):
        pass

    @abc.abstractmethod
    def get_repository_http_url(self, course, team):
        pass

    @abc.abstractmethod
    def get_commit(self, course, team, commit_sha):
        pass

    @abc.abstractmethod
    def create_submission_tag(self, course, team, tag_name, tag_message, commit_sha):
        pass

    @abc.abstractmethod
    def update_submission_tag(self, course, team, tag_name, tag_message, commit_sha):
        pass

    @abc.abstractmethod
    def get_submission_tag(self, course, team, tag_name):
        pass

    @abc.abstractmethod
    def delete_team_repository(self, course, team):
        pass

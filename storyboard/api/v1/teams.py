# Copyright (c) 2014 Mirantis Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from oslo.config import cfg
from pecan.decorators import expose
from pecan import response
from pecan import rest
from pecan.secure import secure
from wsme.exc import ClientSideError
import wsmeext.pecan as wsme_pecan

from storyboard.api.auth import authorization_checks as checks
from storyboard.api.v1 import wmodels
from storyboard.db.api import teams as teams_api
from storyboard.db.api import users as users_api

CONF = cfg.CONF


class UsersSubcontroller(rest.RestController):
    """This controller should be used to list, add or remove users from a Team.
    """

    @secure(checks.guest)
    @wsme_pecan.wsexpose([wmodels.User], int)
    def get(self, team_id):
        """Get users inside a team.

        :param team_id: An ID of the team
        """

        team = teams_api.team_get(team_id)

        if not team:
            raise ClientSideError("The requested team does not exist")

        return [wmodels.User.from_db_model(user) for user in team.users]

    @secure(checks.superuser)
    @wsme_pecan.wsexpose(wmodels.User, int, int)
    def put(self, team_id, user_id):
        """Add a user to a team."""

        teams_api.team_add_user(team_id, user_id)
        user = users_api.user_get(user_id)

        return wmodels.User.from_db_model(user)

    @secure(checks.superuser)
    @wsme_pecan.wsexpose(None, int, int)
    def delete(self, team_id, user_id):
        """Delete a user from a team."""
        teams_api.team_delete_user(team_id, user_id)

        response.status_code = 204


class TeamsController(rest.RestController):
    """REST controller for Teams."""

    @secure(checks.guest)
    @wsme_pecan.wsexpose(wmodels.Team, int)
    def get_one_by_id(self, team_id):
        """Retrieve information about the given team.

        :param team_id: team ID.
        """

        team = teams_api.team_get(team_id)

        if team:
            return wmodels.Team.from_db_model(team)
        else:
            raise ClientSideError("Team %s not found" % team_id,
                                  status_code=404)

    @secure(checks.guest)
    @wsme_pecan.wsexpose(wmodels.Team, unicode)
    def get_one_by_name(self, team_name):
        """Retrieve information about the given team.

        :param team_name: team name.
        """

        team = teams_api.team_get_by_name(team_name)

        if team:
            return wmodels.Team.from_db_model(team)
        else:
            raise ClientSideError("Team %s not found" % team_name,
                                  status_code=404)

    @secure(checks.guest)
    @wsme_pecan.wsexpose([wmodels.Team], int, int, unicode, unicode, unicode,
                         unicode)
    def get(self, marker=None, limit=None, name=None, description=None,
            sort_field='id', sort_dir='asc'):
        """Retrieve a list of teams.

        :param marker: The resource id where the page should begin.
        :param limit: The number of teams to retrieve.
        :param name: A string to filter the name by.
        :param description: A string to filter the description by.
        :param sort_field: The name of the field to sort on.
        :param sort_dir: sort direction for results (asc, desc).
        """
        # Boundary check on limit.
        if limit is None:
            limit = CONF.page_size_default
        limit = min(CONF.page_size_maximum, max(1, limit))

        # Resolve the marker record.
        marker_team = teams_api.team_get(marker)

        teams = teams_api.team_get_all(marker=marker_team,
                                       limit=limit,
                                       name=name,
                                       description=description,
                                       sort_field=sort_field,
                                       sort_dir=sort_dir)

        team_count = teams_api.team_get_count(name=name,
                                              description=description)

        # Apply the query response headers.
        response.headers['X-Limit'] = str(limit)
        response.headers['X-Total'] = str(team_count)
        if marker_team:
            response.headers['X-Marker'] = str(marker_team.id)

        return [wmodels.Team.from_db_model(t) for t in teams]

    @secure(checks.superuser)
    @wsme_pecan.wsexpose(wmodels.Team, body=wmodels.Team)
    def post(self, team):
        """Create a new team.

        :param team: a team within the request body.
        """
        result = teams_api.team_create(team.as_dict())
        return wmodels.Team.from_db_model(result)

    @secure(checks.superuser)
    @wsme_pecan.wsexpose(wmodels.Team, int, body=wmodels.Team)
    def put(self, team_id, team):
        """Modify this team.

        :param team_id: An ID of the team.
        :param team: a team within the request body.
        """
        result = teams_api.team_update(team_id,
                                       team.as_dict(omit_unset=True))

        if result:
            return wmodels.Team.from_db_model(result)
        else:
            raise ClientSideError("Team %s not found" % team_id,
                                  status_code=404)

    users = UsersSubcontroller()

    def _is_int(self, s):
        try:
            int(s)
            return True
        except ValueError:
            return False

    @expose()
    def _route(self, args, request):
        if request.method == 'GET' and len(args) > 0:
            # It's a request by a name or id
            first_token = args[0]
            if self._is_int(first_token):
                if len(args) > 1 and args[1] == "users":
                    # Route to users subcontroller
                    return super(TeamsController, self)._route(args, request)

                # Get by id
                return self.get_one_by_id, args
            else:
                # Get by name
                return self.get_one_by_name, ["/".join(args)]

        # Use default routing for all other requests
        return super(TeamsController, self)._route(args, request)
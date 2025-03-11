from mudforge.portal.commands.base import Command


class _BBSCommand(Command):
    help_category = "Boards"


class BBRead(_BBSCommand):
    name = "bbread"


class BBPost(_BBSCommand):
    name = "bbpost"


class BBReply(_BBSCommand):
    name = "bbreply"

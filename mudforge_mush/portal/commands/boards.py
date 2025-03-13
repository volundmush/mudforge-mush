import pydantic
from collections import defaultdict
from mudforge.portal.commands.base import Command
from mudforge_mush.models import boards as boards_models
from mudforge.utils import partial_match

class _BBSCommand(Command):
    help_category = "Boards"

class BBCreate(_BBSCommand):
    name = "bbcreate"

    async def func(self):
        try:
            board_create = boards_models.BoardCreate(board_key=self.lsargs, name=self.rsargs)
        except pydantic.ValidationError as e:
            raise self.Error(f"Error: {e}")
        board_model = await self.api_character_call("POST", "/boards/", json=board_create.model_dump())
        await self.send_line(f"Board created.")

class BBRead(_BBSCommand):
    name = "bbread"

    async def func(self):
        if not self.lsargs:
            await self.display_boards()
            return
        if "/" in self.lsargs:
            await self.display_post()
        else:
            await self.display_board()

    async def display_boards(self):
        board_list = await self.api_character_call("GET", "/boards/")
        categories = defaultdict(list)
        for board in board_list:
            categories[board["faction_name"]].append(board)

        for faction, boards in categories.items():
            boards.sort(key=lambda x: x["board_order"])
            table = self.make_table("Key", "Name", "Description", title=f"{faction} Boards" if faction else "Public Boards")
            for board in boards:
                table.add_row(board["board_key"], board["name"], board["description"])
            await self.send_rich(table)

    async def display_board(self):
        board_list = await self.api_character_call("GET", "/boards/")
        board = partial_match(self.lsargs, board_list, key=lambda b: b["board_key"])
        post_list = await self.api_character_call("GET", f"/boards/{board['board_key']}/posts")
        table = self.make_table("Key", "Title", "Author", "PostDate", title=board["name"])
        for post in post_list:
            table.add_row(post["post_key"], post["title"], post["spoofed_name"], post["created_at"])
        await self.send_rich(table)

    async def display_post(self):
        board_key, post_key = self.lsargs.split("/", 1)
        board_list = await self.api_character_call("GET", "/boards/")
        board = partial_match(self.lsargs, board_list, key=lambda b: b["board_key"])
        post = await self.api_character_call("GET", f"/boards/{board['board_key']}/posts/{post_key}")
        await self.send_line(post)


class BBPost(_BBSCommand):
    name = "bbpost"

    async def func(self):
        if not "/" in self.lsargs:
            raise self.Error("Syntax: bbpost <board_key>/<title>=<body>")
        board_key, post_title = self.lsargs.split("/", 1)
        try:
            post_model = boards_models.PostCreate(title=post_title, body=self.rsargs)
        except pydantic.ValidationError as e:
            raise self.Error(f"Error: {e}")
        post_model = await self.api_character_call("POST", f"/boards/{board_key}/posts/", json=post_model.model_dump())
        await self.send_line("Post submitted.")

class BBReply(_BBSCommand):
    name = "bbreply"

    async def func(self):
        if not "/" in self.lsargs:
            raise self.Error("Syntax: bbreply <board_key>/<post_key>=<body>")
        board_key, post_key = self.lsargs.split("/", 1)
        try:
            reply_model = boards_models.ReplyCreate(body=self.rsargs)
        except pydantic.ValidationError as e:
            raise self.Error(f"Error: {e}")
        reply_model = await self.api_character_call("POST", f"/boards/{board_key}/posts/{post_key}", json=reply_model.model_dump())
        await self.send_line("Reply submitted.")
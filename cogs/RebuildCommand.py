from discord.ext import commands
import discord
import asyncio
import os
from services import Polygon
import json
from datetime import datetime
from helper import paginator
from helper import helper
from helper import table
import requests
import time


class RebuildCommand(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        username = os.getenv("POLYGON_USERNAME")
        password = os.getenv("POLYGON_PASSWORD")
        api_key = os.getenv("POLYGON_API_KEY")
        api_secret = os.getenv("POLYGON_API_SECRET")

        self.log_channel = None
        self.commit_state = None
        self.interator = Polygon.PolygonInteractor(
            username, password, api_key, api_secret
        )

        self.problem_name_to_id = {}
        self.id_query = 0

    @commands.command(brief="Re-login to polygon")
    @commands.is_owner()
    async def re_login(self, ctx):
        if self.interator.login():
            await ctx.send("VOJ-BOT logged to polygon")
        else:
            await ctx.send("Failed")

    @commands.command(brief="Change log channel.")
    @commands.is_owner()
    async def change_log(self, ctx):
        """Change bot's log channel to this channel"""
        self.log_channel = ctx.channel
        await ctx.send("Successfully set log channel to " + ctx.channel.name)

    @commands.command(brief="Get contest list")
    @commands.is_owner()
    async def contest_list(self, ctx):
        """Get list of contests"""
        # get the first 10 contests
        contests = self.interator.get_contest_list()[:10]

        style = table.Style("{:>}  {:<}  {:<}")
        t = table.Table(style)
        t += table.Header("#", "Name", "Author")
        t += table.Line()
        for contest in contests:
            t += table.Data(*contest)

        msg = "```\n" + str(t) + "\n```"
        await ctx.send(msg)

    # @commands.command(brief="Get contest problem list")
    # @commands.is_owner()
    # async def contest_problem_list(self, ctx, contest_id):
    #     """Get list of problems in a contest"""
    #     problems = self.interator.get_contest_problems(contest_id)

    #     style = table.Style("{:>}  {:<}  {:<} {:<}")
    #     t = table.Table(style)
    #     t += table.Header("#", "Id", "Name", "Author")
    #     t += table.Line()
    #     problemOrders = list(problems.keys())
    #     problemOrders.sort()
    #     for problemOrder in problemOrders:
    #         problem = problems[problemOrder]
    #         t += table.Data(
    #             problemOrder, problem["id"], problem["name"], problem["owner"]
    #         )

    #     msg = "```\n" + str(t) + "\n```"
    #     await ctx.send(msg)

    @commands.command(brief="Get problem tests")
    @commands.is_owner()
    async def problem_tests(self, ctx, problem_id):
        """Get list of tests in a problem"""
        tests = self.interator.get_problem_tests(problem_id)

        total_test = len(tests)
        total_point = 0
        group_test_count = {}
        group_point = {}
        for test in tests:
            group = test.get("group", None)
            points = test.get("points", 0)
            total_point += points

            if group is None:
                continue

            if group not in group_test_count:
                group_test_count[group] = 0
                group_point[group] = 0

            group_test_count[group] += 1
            group_point[group] += points

        if len(group_test_count) == 0:
            msg = f"Total test: {total_test}\nTotal point: {total_point}"
            return await ctx.send(msg)

        style = table.Style("{:<}  {:<}")
        t = table.Table(style)
        t += table.Header("Group", "Tests", "Points")
        t += table.Line()
        for group in group_test_count:
            t += table.Data(group, group_test_count[group], group_point[group])

        msg = "```\n" + str(t) + "\n```"
        msg = f"Total test: {total_test}\nTotal point: {total_point}\n" + msg
        await ctx.send(msg)

    @commands.command(brief="Get contest and problem info")
    @commands.is_owner()
    async def contest_info(self, ctx, contest_id):
        """Get contest and problem info"""
        problems = self.interator.get_contest_info(contest_id)
        style = table.Style("{:>} {:<} {:<} {:<} {:<} {:<} {:<} {:<} {:<}")
        t = table.Table(style)
        t += table.Header(
            "#", "Id", "Name", "Statement", "Tests", "TL", "ML", "Checker", "Rev"
        )
        t += table.Line()
        for problem in problems:
            t += table.Data(*problem)

        msg = str(t)
        if len(msg) > 3000:
            msg = msg[:3000] + "\n..."
        msg = "```\n" + str(t) + "\n```"
        print(len(msg))
        await ctx.send(msg)

    @commands.command(brief="Download all package in a contest")
    @commands.is_owner()
    async def download_contest(
        self,
        ctx,
        contest_id: str = commands.parameter(description="id of contest in polygon"),
        contest_code: str = commands.parameter(description="code of contest in VNOJ"),
    ):
        contest_code = contest_code.rstrip("_")
        errors = []
        import_cmds = []
        submit_cmds = []
        last_message = None

        async def send_message(msg):
            nonlocal last_message
            if last_message is None:
                last_message = await ctx.send(msg)
                return

            last_content = last_message.content
            new_content = last_content + "\n" + msg

            if len(new_content) > 2000:
                new_content = new_content[-2000:]

            last_message = await last_message.edit(content=new_content)

        await send_message("Getting contest info, this may take a while...")
        problems = self.interator.get_contest_info(contest_id)

        for problem in problems:
            [idx, problem_id] = problem[:2]
            idx = str(idx).lower()
            await send_message(f"Downloading {idx}({problem_id})")
            resp = self.interator.download_package(problem_id)
            if resp is None:
                await send_message(f"{idx}({problem_id}) has no linux package")
                continue
            try:
                zip_path = f"/tmp/{idx}.zip"
                with open(zip_path, "wb") as f:
                    f.write(resp.content)

                import_cmd = f"./manage.py import_polygon_package {zip_path} {contest_code}_{idx} --authors bedao"
                submit_cmd = f"./manage.py submit_polygon_solutions {zip_path} {contest_code}_{idx} admin"

                import_cmds.append(import_cmd)
                submit_cmds.append(submit_cmd)
            except Exception as e:
                print(e)
                errors.append(f"Error downloading {idx}({problem_id})")
                continue

        if len(errors) > 0:
            await ctx.send("\n".join(errors))

        msg = " && \ \n".join(import_cmds)
        msg += "\n\n" + " && \ \n".join(submit_cmds)

        print(msg)
        print(len(msg))
        if len(msg) > 3000:
            msg = msg[:3000] + "\n..."
        msg = "```\n" + msg + "\n```"
        await ctx.send(msg)


async def setup(bot: commands.Bot):
    await bot.add_cog(RebuildCommand(bot))

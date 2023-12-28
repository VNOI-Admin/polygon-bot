import requests, random, hashlib, time, re

from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

BASE_URL = "https://polygon.codeforces.com"


class PolygonInteractor:
    def __init__(self, username, password, api_key, api_secret):
        self.username = username
        self.password = password
        self.api_key = api_key
        self.api_secret = api_secret

        s = requests.session()
        s.allow_redirects = False

        # For debugging
        # s.proxies = {'http': 'http://localhost:8888', 'https': 'http://localhost:8888'}
        # s.verify = False

        self.s = s

        # self.login()
        self.session_id_cache = {}
        self.contest_list_cache = None
        self.contest_problem_list_cache = {}

    def extract_ccid(self, text):
        return text.split('name="ccid" content="')[1].split('"')[0]

    def clear_cache(self):
        self.session_id_cache = {}
        self.contest_list_cache = None

    # login with self.username & self.password
    def login(self):
        self.clear_cache()

        r = self.s.get(BASE_URL + "/login")
        ccid = self.extract_ccid(r.text)
        self.ccid = ccid

        data = {
            "login": self.username,
            "password": self.password,
            "submit": "Login",
            "submitted": "true",
        }

        params = {"ccid": ccid}

        r1 = self.s.post(
            BASE_URL + "/login", data=data, params=params, allow_redirects=False
        )

        if r1.status_code != 302:
            return False

        print(self.username + " logged to polygon")
        return True

    def get_session_id(self, problem_id):
        if problem_id in self.session_id_cache:
            return self.session_id_cache[problem_id]
        data = {"problemId": problem_id}
        params = {"ccid": self.ccid}

        continue_edit_request = self.s.post(
            BASE_URL + "/edit-start", data=data, params=params, allow_redirects=False
        )

        session = parse_qs(urlparse(continue_edit_request.headers["location"]).query)[
            "session"
        ][0]

        self.session_id_cache[problem_id] = session
        return session

    def request_unofficial(
        self, method_name, data=None, params=None, method="GET", allow_redirects=False
    ):
        if params is None:
            params = {}
        if data is None:
            data = {}

        data["ccid"] = self.ccid
        params["ccid"] = self.ccid

        if "problemId" in data and "session" not in data:
            data["session"] = self.get_session_id(data["problemId"])

        if "problemId" in params and "session" not in params:
            params["session"] = self.get_session_id(params["problemId"])

        return self.s.request(
            method,
            BASE_URL + "/" + method_name,
            files=data,
            params=params,
            allow_redirects=allow_redirects,
        )

    def request_official(self, method_name, data=None, params=None, method="POST"):
        if params is None:
            params = {}
        if data is None:
            data = {}

        params["apiKey"] = self.api_key
        params["time"] = int(time.time())

        signature_random = "".join(
            [chr(random.SystemRandom().randint(0, 25) + ord("a")) for _ in range(6)]
        )
        signature_random = signature_random.encode("utf-8")

        for i in params:
            params[i] = str(params[i]).encode("utf-8")
        param_list = [(key.encode("utf-8"), params[key]) for key in params]
        param_list.sort()

        signature_string = signature_random + b"/" + method_name.encode("utf-8")
        signature_string += b"?" + b"&".join([i[0] + b"=" + i[1] for i in param_list])
        signature_string += b"#" + self.api_secret.encode("utf-8")
        params["apiSig"] = signature_random + hashlib.sha512(
            signature_string
        ).hexdigest().encode("utf-8")
        url = BASE_URL + "/api/" + method_name

        return self.s.request(method, url, files=params)

    def get_problem_list(self):
        return self.request_official("problems.list").json()["result"]

    def give_access(self, problem_id, usernames, write=False, session=None):
        # give username permission to problem

        data = {
            "problemId": str(problem_id),
            "submitted": "true",
            "users_added": ",".join(usernames),
            "type": "Write" if write else "Read",
            "session": session,
        }

        r = self.request_unofficial(
            "access", data=data, params={"action": "add"}, method="POST"
        )
        return "location" in r.headers and "access" in r.headers["location"]

    def upload_solution(self, problem_id, name, content):
        params = {
            "problemId": problem_id,
            "checkExisting": True,
            "name": name,
            "file": content,
            "tag": "OK",
        }
        return self.request_official("problem.saveSolution", params=params).text

    def upload_test(
        self, problem_id, test_index, content, description="uploaded by bot"
    ):
        params = {
            "problemId": problem_id,
            "testset": "tests",
            "testIndex": test_index,
            "testInput": content,
            "checkExisting": "true",
            "testDescription": description,
        }
        return self.request_official("problem.saveTest", params=params).text

    def commit(self, problem_id, message="Commited by bot"):
        data = {
            "submitted": "true",
            "message": message,
            "problemId": problem_id,
            "minorChanges": "on",
            "allContests": "true",
        }
        return self.request_unofficial(
            "edit-commit", data=data, params={"action": "add"}, method="POST"
        ).status_code

    def get_current_working_copy(self, page):
        text = self.s.request(
            "GET", BASE_URL + "/problems?page=" + str(page) + "&ccid=" + str(self.ccid)
        ).text
        p = r"\/edit-stop\?workingCopyId=(\d+)"
        return re.findall(p, text)

    def get_polygon_link(self, problem_id):
        data = {
            "problemId": str(problem_id),
            "ccid": self.ccid,
        }

        r = self.s.request(
            "GET", BASE_URL + "/generalInfo", params=data, allow_redirects=False
        )
        soup = BeautifulSoup(r.text, features="html.parser")
        links = soup.find(
            "div",
            {
                "style": "font-size:11px;text-align:right;color:gray;overflow-wrap:break;word-break: break-all;padding-top:5px;"
            },
        )
        return links.text.strip()

    def create_package(self, problem_id):
        data = {"problemId": problem_id}
        params = {"action": "create", "createFull": "true"}

        r = self.request_unofficial("package", data=data, params=params, method="POST")

    def discard_current_working_copy(self, id):
        data = {"workingCopyId": id}
        return self.request_unofficial(
            "edit-stop", data=data, method="POST"
        ).status_code

    def get_problem_list(self):
        return self.request_official("problems.list").json()["result"]

    def get_package_link(self, problem_id):
        data = {
            "problemId": str(problem_id),
        }
        resp = self.request_unofficial("package", params=data)
        soup = BeautifulSoup(resp.text, features="html.parser")

        package_table = soup.find_all("table", {"class": "grid tablesorter"})[0]

        latest_package = package_table.find_all("tr")[1]
        links_cell = latest_package.find_all("td", {"align": "center"})[0]
        links = links_cell.find_all("div")

        for l in links:
            if l.text.strip() == "Linux":
                return l.a["href"]
        return None

    def download_package(self, problem_id):
        link = self.get_package_link(problem_id)
        if link is None:
            return None

        resp = self.request_unofficial(
            link,
            params={"session": self.get_session_id(problem_id)},
            allow_redirects=False,
        )
        return resp

    def get_contest_list(self):
        if self.contest_list_cache is not None:
            return self.contest_list_cache

        resp = self.request_unofficial("contests")
        soup = BeautifulSoup(resp.text, features="html.parser")
        contest_table = soup.select("table.contest-list-grid")[0]

        def get_row_data(row):
            tds = row.find_all("td")
            if len(tds) == 0:
                return None
            cells = [" ".join(t.text.split()) for t in tds]

            contest_id = cells[1]
            contest_name = cells[2][: cells[2].find("problems")]
            author = cells[3]
            return [contest_id, contest_name, author]

        rows = [get_row_data(row) for row in contest_table.find_all("tr")[2:]]
        self.contest_list_cache = rows
        return rows

    def get_contest_problems(self, contest_id):
        if contest_id in self.contest_problem_list_cache:
            return self.contest_problem_list_cache[contest_id]

        result = self.request_official(
            "contest.problems", params={"contestId": contest_id}
        ).json()["result"]

        self.contest_problem_list_cache[contest_id] = result
        return result

    def get_problem_tests(self, problem_id):
        return self.request_official(
            "problem.tests",
            params={"problemId": problem_id, "noInputs": True, "testset": "tests"},
        ).json()["result"]

    def get_contest_info(self, contest_id):
        resp = self.request_unofficial("contest", params={"contestId": contest_id})
        soup = BeautifulSoup(resp.text, features="html.parser")
        problem_table = soup.select("table.problem-list-grid")[0]

        def get_row_data(row):
            tds = row.find_all("td")
            if len(tds) == 0:
                return None
            cells = [" ".join(t.text.split()) for t in tds]
            try:
                problem_id = row.get("problemid")
                problem_name = row.get("problemname")
                idx = cells[4]
                rev = " ".join(cells[6].split(" ")[:3])
            except Exception as e:
                print(e)
                return None

            try:
                details = [
                    " ".join(x.split())
                    for x in tds[5].text.strip().split("\n")
                    if " ".join(x.split()) != ""
                ]

                statement = details[0]
                tests = details[1]
                if tests.startswith("tests("):
                    tests = tests.split(")")[0].split("(")[1]
                tl, ml = [x.strip() for x in details[2].split("/")]
                tl = tl.split(" ")[0]
                checker = details[5]
            except:
                print(e)
                statement = "-"
                tests = "-"
                tl = "-"
                ml = "-"
                checker = "-"
            return [
                idx,
                problem_id,
                problem_name,
                statement,
                tests,
                tl,
                ml,
                checker,
                rev,
            ]

        rows = [get_row_data(row) for row in problem_table.find_all("tr")[2:]]
        return rows

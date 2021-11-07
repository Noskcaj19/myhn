from typing import Optional
from fastapi import FastAPI, Response, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
import httpx
import urllib.parse
import asyncio
from postgres import Postgres
import os


templates = Jinja2Templates(directory="templates")
db = Postgres(os.environ["POSTGRES_DB"])
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")


async def get_item(id: int, client: httpx.AsyncClient):
    item = (
        await client.get(
            f"https://hacker-news.firebaseio.com/v0/item/{id}.json?print=pretty"
        )
    ).json()
    if "url" in item:
        item["domain"] = urllib.parse.urlsplit(item["url"]).hostname
    return {k: v for k, v in item.items() if type(v) != list}


async def top_items(page: int):
    async with httpx.AsyncClient() as client:
        r = await client.get("https://hacker-news.firebaseio.com/v0/topstories.json")
        items = list(
            map(
                lambda id: get_item(id, client),
                r.json()[30 * (page - 1) : 30 * page],
            )
        )

        return await asyncio.gather(*items)


@app.get("/dislike/{item}")
async def redir(item: int):
    db.run(
        r"""
update items set disliked = true where id = %(id)s
""",
        {"id": item},
    )
    return RedirectResponse("/top")


@app.get("/redir/{item}")
async def redir(item: int):
    async with httpx.AsyncClient() as client:
        url = (await get_item(item, client))["url"]
    db.run(
        r"""
update items set read_article = true where id = %(id)s
""",
        {"id": item},
    )
    return RedirectResponse(url)


@app.get("/redir/{item}/comments")
async def redir_comments(item: int):
    db.run(
        r"""
update items set read_comments = true where id = %(id)s
""",
        {"id": item},
    )
    return RedirectResponse(f"https://news.ycombinator.com/item?id={item}")


@app.get("/top", response_class=HTMLResponse)
@app.get("/top/{page}", response_class=HTMLResponse)
async def top(request: Request, response: Response, page: Optional[int] = 1):
    try:
        stories = list(await top_items(page))
    except httpx.ConnectError:
        response.code = 500
        return
    for item in stories:
        db.run(
            r"""
insert into items values (%(id)s, %(title)s, %(url)s, false, false, false)
on conflict (id) do nothing
""",
            {"id": item["id"], "title": item["title"], "url": item.get("url")},
        )

    return templates.TemplateResponse(
        "top.html.jinja", {"request": request, "stories": stories, "page": page}
    )

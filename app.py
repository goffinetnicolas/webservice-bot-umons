import os
from flask import Flask, request
from github import Github, GithubIntegration

app = Flask(__name__)

app_id = '311878'

# Read the bot certificate
with open(
        os.path.normpath(os.path.expanduser('bot_key.pem')),
        'r'
) as cert_file:
    app_key = cert_file.read()
    
# Create an GitHub integration instance
git_integration = GithubIntegration(
    app_id,
    app_key,
)

def issue_opened_event(repo, payload):
    issue = repo.get_issue(number=payload["issue"]["number"])
    author = issue.user.login

    response = (
        f"Thanks for opening this issue, @{author}! "
        f"The repository maintainers will look into it ASAP! :speech_balloon:"
    )
    issue.add_to_labels("urgent")
    issue.create_comment(f"{response}")


def pull_request_close_event(repo, payload):
    pull = repo.get_pull(number=payload['number'])
    if pull.merged:
        pull.create_issue_comment("Thanks for your contribution")
        gref = repo.get_git_ref(f"heads/{pull.head.ref}")
        gref.delete()

keyword=["wip", "work in progress", "do not merge"]

def check_wip(repo, payload, prec=None):
    pull = repo.get_pull(number=payload['number'])
    name = pull.title.lower()
    wip_check = prec and any(wip in prec.lower() for wip in keyword)
    if any(wip in name for wip in keyword):
        if not wip_check:
            pull.create_issue_comment("pull request is in work in progress.")
        pull.get_commits().reversed[0].create_status(
            state='pending',
            description='Work in progress',
            context='WIP'
        )
    elif wip_check:
        pull.create_issue_comment("pull request available for review.")
        pull.get_commits().reversed[0].create_status(
            state='success',
            description='Ready for review',
            context='WIP'
        )


def pull_request_edited(repo, payload):
    prec = None
    if 'title' in payload['changes']:
        prec = payload['changes']['title']['from']
    check_wip(repo, payload, prec=prec)


def pull_request_opened(repo, payload):
    check_wip(repo, payload)

@app.route("/", methods=['POST'])
def bot():
    payload = request.json

    if not 'repository' in payload.keys():
        return "", 204

    owner = payload['repository']['owner']['login']
    repo_name = payload['repository']['name']

    git_connection = Github(
        login_or_token=git_integration.get_access_token(
            git_integration.get_installation(owner, repo_name).id
        ).token
    )
    repo = git_connection.get_repo(f"{owner}/{repo_name}")

    if all(k in payload.keys() for k in ['action', 'issue']) and payload['action'] == 'opened':
        issue_opened_event(repo, payload)
    elif all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'closed':
        pull_request_close_event(repo, payload)
    elif all(k in payload.keys() for k in ['action', 'pull_request']) and payload['action'] == 'opened':
        pull_request_opened(repo, payload)
    elif all(k in payload.keys() for k in ['action', 'issue']) and payload['action'] == 'edited':
        pull_request_edited(repo, payload)

    return "", 204

if __name__ == "__main__":
    app.run(debug=True, port=5000)

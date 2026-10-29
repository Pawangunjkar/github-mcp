# github-mcp tool catalog

80 tools. `session_name` selects the cached GitHub session and defaults to `default`.

## Connection and authentication (4)

| Tool | Description |
|------|-------------|
| `github_connect` | Open a session with a personal access token |
| `github_disconnect` | Close one named session |
| `github_status` | Show the authenticated user and rate limits |
| `github_save_credentials` | Cache a token for a session name |

## Repositories (10)

| Tool | Description |
|------|-------------|
| `github_list_repos` | List repositories for the user or an owner |
| `github_get_repo` | Get repository metadata |
| `github_create_repo` | Create a repository |
| `github_delete_repo` | Delete a repository |
| `github_fork_repo` | Fork a repository |
| `github_update_repo` | Update repository settings |
| `github_list_topics` | List repository topics |
| `github_update_topics` | Replace repository topics |
| `github_list_languages` | Get the language breakdown |
| `github_list_contributors` | List contributors |

## Branches and tags (8)

| Tool | Description |
|------|-------------|
| `github_list_branches` | List branches |
| `github_get_branch` | Get one branch and its protection state |
| `github_create_branch` | Create a branch from a ref |
| `github_delete_branch` | Delete a branch |
| `github_protect_branch` | Set branch protection |
| `github_list_tags` | List tags |
| `github_create_tag` | Create a tag |
| `github_compare_branches` | Compare two refs |

## Files (6)

| Tool | Description |
|------|-------------|
| `github_get_file` | Read a file, decoding base64 content |
| `github_create_file` | Commit a new file |
| `github_update_file` | Commit a change to an existing file |
| `github_delete_file` | Delete a file by commit |
| `github_get_tree` | List a git tree |
| `github_get_clone_url` | Return the SSH or HTTPS clone URL |

## Pull requests (10)

| Tool | Description |
|------|-------------|
| `github_list_prs` | List pull requests |
| `github_get_pr` | Get one pull request |
| `github_create_pr` | Open a pull request |
| `github_update_pr` | Update a pull request |
| `github_merge_pr` | Merge a pull request |
| `github_close_pr` | Close a pull request |
| `github_list_pr_files` | List files changed in a pull request |
| `github_list_pr_reviews` | List reviews |
| `github_request_reviewers` | Request reviewers |
| `github_create_pr_comment` | Comment on a pull request |

## Issues (8)

| Tool | Description |
|------|-------------|
| `github_list_issues` | List issues |
| `github_get_issue` | Get one issue |
| `github_create_issue` | Open an issue |
| `github_update_issue` | Update an issue |
| `github_close_issue` | Close an issue |
| `github_create_issue_comment` | Comment on an issue |
| `github_list_issue_comments` | List issue comments |
| `github_add_labels` | Add labels to an issue or pull request |

## Actions and CI/CD pipelines (14)

| Tool | Access | Description |
|------|--------|-------------|
| `github_list_workflows` | Read-only | List workflow ids and filenames |
| `github_trigger_workflow` | Mutating | Dispatch `workflow_dispatch` |
| `github_list_workflow_runs` | Read-only | List runs, including `run_id` |
| `github_get_workflow_run` | Read-only | Get status, conclusion, SHA, and URL |
| `github_get_run_logs` | Read-only | Point at the log archive; does not inline the zip |
| `github_cancel_workflow_run` | Mutating | Cancel an in-progress run |
| `github_rerun_workflow` | Mutating | Rerun every job |
| `github_generate_action_pipeline` | Preview, or confirm to commit | Write `.github/workflows/<name>.yml` for GitHub Packages, Nexus, Artifactory, or ECR/ACR/GAR, with an optional OpenShift, EKS, AKS, or GKE deploy job |
| `github_get_failed_job_logs` | Read-only | Return failing step names and a short error excerpt |
| `github_rerun_failed_jobs` | Confirm (`confirm=true`) | POST `rerun-failed-jobs` |
| `github_get_run_artifacts_metadata` | Read-only | List artifact id, size, SHA256, expiry, and download URL |
| `github_get_pending_deployments` | Read-only | List environment gates waiting on a run |
| `github_review_Pending_deployment` | Confirm (`confirm=true`) | Approve or reject a pending environment deployment |
| `github_check_ci_secrets_and_variables` | Read-only | List variable names and values, and secret names only |

`github_generate_action_pipeline` parameters:

- `language`: `python`, `node`, `java`, `go`, `dotnet`, `generic`
- `build_tool`: tool paired with that language; empty uses the default
- `artifact_target`: `github_packages`, `nexus`, `artifactory`, `ecr_acr_gar`
- `deploy_target`: `openshift`, `eks`, `aks`, `gke`, `none`
- `registry_cloud`: `ecr`, `acr`, or `gar` when the artifact target is `ecr_acr_gar`
- `commit` and `confirm`: both must be true before the workflow file is committed

## Releases (5)

| Tool | Description |
|------|-------------|
| `github_list_releases` | List releases |
| `github_get_release` | Get one release and its assets |
| `github_create_release` | Create a release |
| `github_delete_release` | Delete a release |
| `github_get_latest_release` | Get the latest release |

## Users and organizations (5)

| Tool | Description |
|------|-------------|
| `github_get_user` | Get a user profile, or the authenticated user |
| `github_list_user_repos` | List repositories for a user |
| `github_get_org` | Get an organization |
| `github_list_org_repos` | List organization repositories |
| `github_list_org_members` | List organization members |

## Search (4)

| Tool | Description |
|------|-------------|
| `github_search_repos` | Search repositories |
| `github_search_code` | Search code |
| `github_search_issues` | Search issues and pull requests |
| `github_search_users` | Search users and organizations |

## Gists (4)

| Tool | Description |
|------|-------------|
| `github_list_gists` | List gists |
| `github_create_gist` | Create a gist |
| `github_get_gist` | Get gist contents |
| `github_delete_gist` | Delete a gist |

## Notifications (2)

| Tool | Description |
|------|-------------|
| `github_list_notifications` | List notifications |
| `github_mark_notifications_read` | Mark notifications as read |

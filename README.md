# Minecraft Control Panel - Gist Suggestions v2

This version parses issue content like this:

```txt
New gist suggestion submitted from the Minecraft Panel settings.

Requested by: admin
Target gist: https://gist.github.com/surgamingoninsulin/2b4d90991a5a5a025f69cce2282f67b7

Suggestion payload:

{
  "plugins": [
    {
      "id": "example-plugin",
      "name": "Example Plugin",
      "author": "Example Author",
      "minecraftVersion": "1.21.11",
      "version": "1.0.0",
      "image": "https://example.com/logo.png",
      "directDownloadUrl": "https://example.com/download.jar",
      "description": "Example description",
      "websiteUrl": "https://example.com",
      "dependencies": []
    }
  ]
}
```

No fenced json code block is required.

## Imported sections

Only these are imported:

```txt
plugins
datapacks
mods
```

Ignored:

```txt
resourcepacks
all unknown sections
```

## Behavior

Input:

```json
{
  "plugins": [
    {
      "id": "example-plugin"
    }
  ]
}
```

The importer appends only this inner item to the bottom of the existing `plugins` list:

```json
{
  "id": "example-plugin"
}
```

It never imports the wrapper object itself.

## Workflow

Runs every 5 minutes:

```yaml
schedule:
  - cron: "*/5 * * * *"
```

Also runs when issues are opened, edited, reopened, or labeled.

## Required secrets

```txt
GITHUB_ISSUE_TOKEN
GIST_ID
```

Optional:

```txt
GIST_TOKEN
```

## Token permissions

For issue reading/commenting/labeling:

```txt
Repository permissions:
- Issues: Read and write
- Metadata: Read
```

For Gist updating:

```txt
User permissions:
- Gists: Read and write
```

## Important

Set this to the real filename inside the Gist:

```txt
GIST_FILENAME=gist_provider.json
```

If your Gist file has another filename, update it in:

```txt
.github/workflows/apply-gist-suggestions.yml
```

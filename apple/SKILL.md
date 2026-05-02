---
name: apple
description: "Apple/macOS productivity skills — iMessage, Reminders, Notes, and FindMy device tracking. These skills only load on macOS systems. Use when user wants to send iMessages, manage reminders, access notes, or track Apple devices/AirTags."
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [macos]
metadata:
  hermes:
    tags: [Apple, macOS, iMessage, Reminders, Notes, FindMy, AirTag, location, automation]
    umbrella: true
---

# Apple Platform Skills

Apple/macOS-specific productivity tools. All skills require macOS with the relevant Apple apps signed in.

## Quick Decision Tree

| User wants | § to use |
|------------|----------|
| Send/receive iMessage or SMS | § iMessage |
| Create/list/complete reminders that sync to iPhone | § Reminders |
| Create/view/search Apple Notes | § Notes |
| Track Apple devices or AirTags | § FindMy |

## § iMessage — Send and Receive iMessages/SMS

**Use for:** Read and send iMessage/SMS via macOS Messages.app.

**Prerequisites:** `brew install steipete/tap/imsg`, Full Disk Access, Automation permission for Messages.app.

**Quick reference:**
```bash
# List chats
imsg chats --limit 10 --json

# Send message
imsg send --to "+141****1212" --text "Hello!"

# With attachment
imsg send --to "+141****1212" --text "Check this out" --file /path/to/image.jpg

# Force iMessage or SMS
imsg send --to "+141****1212" --text "Hi" --service imessage
imsg send --to "+141****1212" --text "Hi" --service sms

# View history
imsg history --chat-id 1 --limit 20 --json
```

**Rules:**
1. Always confirm recipient and message content before sending
2. Never send to unknown numbers without explicit user approval
3. Verify file paths exist before attaching

## § Reminders — Apple Reminders

**Use for:** Manage Apple Reminders that sync across all Apple devices via iCloud.

**Prerequisites:** `brew install steipete/tap/remindctl`, Reminders permission.

**Quick reference:**
```bash
remindctl                    # Today's reminders
remindctl today              # Today
remindctl tomorrow           # Tomorrow
remindctl week               # This week
remindctl overdue            # Past due

# Create
remindctl add --title "Call mom" --list Personal --due tomorrow
remindctl add --title "Meeting prep" --due "2026-02-15 09:00"

# Complete / Delete
remindctl complete 1 2 3
remindctl delete 4A83 --force

# Lists
remindctl list               # All lists
remindctl list Work --create # Create list
```

**When to use Apple Reminders vs cronjob:** Use Reminders when tasks need to appear on iPhone/iPad. Use cronjob for agent-side scheduling that doesn't need device sync.

## § Notes — Apple Notes

**Use for:** Create, view, search, and manage Apple Notes via the `memo` CLI.

**Prerequisites:** `brew tap antoniorodr/memo && brew install antoniorodr/memo/memo`, Automation access to Notes.app.

**Quick reference:**
```bash
memo notes                        # List all notes
memo notes -f "Folder Name"       # Filter by folder
memo notes -s "query"             # Search notes (fuzzy)
memo notes -a "Note Title"        # Quick add with title
memo notes -e                     # Edit (interactive)
memo notes -d                     # Delete (interactive)
memo notes -ex                    # Export to HTML/Markdown
```

**Limitations:**
- Cannot edit notes containing images or attachments
- Interactive prompts require terminal access

**When to use vs obsidian:** Use Apple Notes when user wants cross-device sync (iPhone/iPad/Mac). Use `obsidian` for Markdown-native knowledge management.

## § FindMy — Apple Device and AirTag Tracking

**Use for:** Track Apple devices and AirTags via the FindMy.app on macOS using AppleScript and screen capture.

**Prerequisites:** Screen Recording permission, optional `peekaboo` for better UI automation.

**Quick reference:**
```bash
# Method 1: AppleScript + Screenshot
osascript -e 'tell application "FindMy" to activate'
sleep 3
screencapture -w -o /tmp/findmy.png
# Then vision_analyze the screenshot

# Method 2: Peekaboo (recommended)
peekaboo see --app "FindMy" --annotate --path /tmp/findmy-ui.png
peekaboo image --app "FindMy" --path /tmp/findmy-detail.png

# Track AirTag over time
while true; do
    screencapture -w -o /tmp/findmy-$(date +%H%M%S).png
    sleep 300
done
```

**Limitations:**
- FindMy has no CLI or API — UI automation required
- AirTags only update location while FindMy page is actively displayed
- Screen Recording permission required

**Rules:**
1. Keep FindMy app in foreground when tracking AirTags
2. Use `vision_analyze` to read screenshot content
3. For ongoing tracking, use a cronjob to periodically capture and log locations

---

## Sub-Skill Reference

| Sub-skill | Location | Status |
|-----------|----------|--------|
| apple-notes | `apple/apple-notes/SKILL.md` | Absorbed → § Notes |
| apple-reminders | `apple/apple-reminders/SKILL.md` | Absorbed → § Reminders |
| findmy | `apple/findmy/SKILL.md` | Absorbed → § FindMy |
| imessage | `apple/imessage/SKILL.md` | Absorbed → § iMessage |

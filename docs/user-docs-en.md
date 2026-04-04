# Eyestream — User Guide

> This guide explains how to upload, manage, and embed videos on your website or knowledge base.

> **Note:** Access to the video management system is restricted to authorized users. If you don't have access, contact IT.

## Login

Open the admin URL and sign in with your account.

> **Screenshot suggestion:** Login splash screen with logo and flame animation.

## Uploading Videos

1. Click **Upload Video** in the top right corner
2. Drag the video file into the upload area or click **Choose File**
3. Select a **Category** (e.g., "Marketing: Website" or "Knowledge Base: Training")
4. Optional: Add a **Note** (e.g., where the video will be embedded)
5. Click **Start Upload**

> **Screenshot suggestion:** Upload page with selected file, category dropdown, and note.

After uploading, the video is automatically encoded into multiple quality levels. You can track the progress live on the overview page.

## Overview

The home page displays all videos with thumbnails, titles, and technical information.

> **Screenshot suggestion:** Video overview with multiple video cards.

### Search and Filter

- **Search field**: Start typing — suggestions appear instantly
- **Category filter**: Select a category from the dropdown to show only videos from that category

### Edit a Video

- **Change title**: Double-click the title or click the pencil icon
- **Edit note**: Click the note field and type
- **Change category**: Click the orange category dropdown and select a different category

### Change the Poster Image

1. Click the thumbnail to open the player
2. Navigate to the desired position in the video
3. **Pause** the video
4. Click the **Set Poster** button (appears at the top of the player)

The poster image is extracted in high quality directly from the original video.

> **Screenshot suggestion:** Video player with paused video and "Set Poster" button.

## Embedding Videos

Each video has two URLs:

### Copy URL (for your website)

The streaming URL (`.m3u8`) for technical integration on your website. The poster image URL can be derived by replacing `master.m3u8` with `poster.jpg`. The example page (link "Example" in the header) provides ready-to-use code.

### Copy Player URL (for the knowledge base)

A ready-made player page with poster image. Ideal for **Outline Wiki**:

1. Copy the player URL
2. Paste it in Outline
3. Click **Embed**

The video will be embedded with a poster image and play button. Hovering over it automatically shows preview images from the video.

> **Screenshot suggestion:** Outline Wiki with embedded video player.

The **?** button next to the copy buttons opens an explanation of both options.

## Disabling a Video

You can temporarily disable a video without deleting it. Disabled videos are no longer accessible on the website or in the knowledge base.

1. Click **Disable** on the video
2. Confirm with a second click

The video will be shown in the overview with a "DISABLED" banner and a hatched background. You can still play and edit it — only the public delivery is stopped.

To re-enable, click **Enable**.

## Categories

Categories help with organization. Each video belongs to a category (e.g., "Marketing: Website", "Knowledge Base: Training").

Manage categories under **Settings** (gear icon in the header):
- Create a new category
- Rename or delete existing ones
- Click a category to open the filtered video overview

## Theme

Click the sun/moon icon in the header to switch between light, dark, and automatic themes:
- Sun: Light
- Moon: Dark
- Half: Automatic (follows your system setting)

## Items per Page

In the page navigation on the right, you can choose how many videos to display per page: 10, 20, 50, 100, or All. The setting is saved.

## Statistics

Click the chart icon in the header to open the statistics page:
- Number of videos and total duration
- Storage overview (pie chart)
- Loads over the last 4 days (trend graph)
- Top websites embedding your videos

> **Screenshot suggestion:** Statistics page with tiles, pie chart, and trend graph.

## Activity Log

Access the activity log via the clock icon in the header. Here you can see who uploaded, edited, disabled, or deleted which video and when.

> **Screenshot suggestion:** Activity log with colored entries.

## Tips

- **Hover preview**: Move your mouse over a thumbnail — different scenes from the video are shown automatically
- **Referer badges**: The small colored badges on the thumbnail show how often and from which websites the video was accessed
- **Duration badge**: Bottom left on the thumbnail shows the video duration
- **Quick search**: Start typing — suggestions appear instantly, including categories

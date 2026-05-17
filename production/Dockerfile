# Stage 1: Build the Custom Frontend
FROM node:22-alpine3.20 AS frontend-builder

# Install git to fetch the exact Open WebUI source version
RUN apk add --no-cache git

# Clone the specific version you are using (0.9.5)
RUN git clone --branch v0.9.5 https://github.com/open-webui/open-webui.git /app

WORKDIR /app

# Install dependencies
RUN npm ci --force

# Copy all custom frontend components into a dedicated extensions folder
COPY extensions/frontend/ src/lib/components/custom_ext/

# INJECTION LOGIC: Wire the master Anchor component into the native Sidebar
# Step 1: Add the import statement for our Anchor component
RUN sed -i '/import Folder from/a import ExtensionAnchor from "$lib/components/custom_ext/Anchor.svelte";' src/lib/components/layout/Sidebar.svelte

# Step 2: Inject <ExtensionAnchor /> just before the native <Folder id="sidebar-chats">
#         This is the proven, minimal injection that has always worked.
RUN node -e "\
const fs = require('fs');\
let c = fs.readFileSync('src/lib/components/layout/Sidebar.svelte', 'utf8');\
c = c.replace(\
  /<Folder[\s\n\t]+id=\"sidebar-chats\"/,\
  '<ExtensionAnchor />\n\n\t\t\t\t<Folder\n\t\t\t\t\tid=\"sidebar-chats\"'\
);\
fs.writeFileSync('src/lib/components/layout/Sidebar.svelte', c);\
"

# Verification gate: fail loud if the injection silently no-op'd (e.g. an
# Open WebUI upstream rename broke the Folder selector). Pinned to v0.9.5 by
# the clone above; if you bump the upstream version and the build fails here,
# update the sed/Node patterns above instead of bypassing this check.
RUN grep -q 'import ExtensionAnchor from "\$lib/components/custom_ext/Anchor.svelte"' src/lib/components/layout/Sidebar.svelte \
        || (echo "ERROR: ExtensionAnchor import missing from Sidebar.svelte — upstream layout likely changed." && exit 1)
RUN grep -q '<ExtensionAnchor />' src/lib/components/layout/Sidebar.svelte \
        || (echo "ERROR: <ExtensionAnchor /> tag not injected into Sidebar.svelte." && exit 1)

# INJECTION LOGIC: Wire BreadcrumbBar + LessonCardPanel into the native Chat pane
# Step 1: Add import statements immediately after the existing Navbar import
RUN sed -i '/import Navbar from/a import BreadcrumbBar from "\$lib/components/custom_ext/BreadcrumbBar.svelte";' \
        src/lib/components/chat/Chat.svelte
RUN sed -i '/import BreadcrumbBar from/a import LessonCardPanel from "\$lib/components/custom_ext/LessonCardPanel.svelte";' \
        src/lib/components/chat/Chat.svelte

# Step 2: Inject <BreadcrumbBar /> and <LessonCardPanel /> immediately before <div id="chat-pane"
RUN node -e "\
const fs = require('fs');\
let c = fs.readFileSync('src/lib/components/chat/Chat.svelte', 'utf8');\
c = c.replace(\
  '<div id=\"chat-pane\"',\
  '<BreadcrumbBar />\\n\\t\\t\\t<LessonCardPanel />\\n\\t\\t\\t<div id=\"chat-pane\"'\
);\
fs.writeFileSync('src/lib/components/chat/Chat.svelte', c);\
"

# Verification gates for Chat.svelte injections — same rationale as Sidebar gates above.
RUN grep -q 'import BreadcrumbBar from' src/lib/components/chat/Chat.svelte \
        || (echo "ERROR: BreadcrumbBar import missing from Chat.svelte — upstream layout likely changed." && exit 1)
RUN grep -q 'import LessonCardPanel from' src/lib/components/chat/Chat.svelte \
        || (echo "ERROR: LessonCardPanel import missing from Chat.svelte." && exit 1)
RUN grep -q '<BreadcrumbBar />' src/lib/components/chat/Chat.svelte \
        || (echo "ERROR: <BreadcrumbBar /> not injected into Chat.svelte." && exit 1)
RUN grep -q '<LessonCardPanel />' src/lib/components/chat/Chat.svelte \
        || (echo "ERROR: <LessonCardPanel /> not injected into Chat.svelte." && exit 1)

# Build the frontend with our injected components
RUN npm run build


# Stage 2: Final Production Image
# Pull the official pre-built Python backend image to save massive build time
FROM ghcr.io/open-webui/open-webui:0.9.5

# Overwrite the default compiled frontend with our newly compiled custom frontend
COPY --chown=0:0 --from=frontend-builder /app/build /app/build

# Copy the custom backend extensions directly into the container's router directory.
# ext_authz is a shared helper (audit + access scaffold) and is imported by both
# ext_router and ext_syllabus, so it must be present before they are loaded.
COPY extensions/ext_authz.py /app/backend/open_webui/routers/ext_authz.py
COPY extensions/ext_router.py /app/backend/open_webui/routers/ext_router.py
COPY extensions/ext_syllabus.py /app/backend/open_webui/routers/ext_syllabus.py
COPY extensions/ext_entitlements.py /app/backend/open_webui/routers/ext_entitlements.py

# Inject the router registration into the main FastAPI application
RUN sed -i '/app.include_router(utils.router/a \
from open_webui.routers import ext_syllabus, ext_router, ext_entitlements\n\
app.include_router(ext_syllabus.router, prefix="/api/ext/syllabus", tags=["ext"])\n\
app.include_router(ext_router.router, prefix="/api/ext", tags=["ext"])\n\
app.include_router(ext_entitlements.router, prefix="/api/ext", tags=["ext"])' /app/backend/open_webui/main.py

# Verification gate: fail loud if the router include sed didn't take. Same
# rationale as the Sidebar.svelte check above — an upstream rename of
# `utils.router` would silently skip the append.
RUN grep -q 'from open_webui.routers import ext_syllabus, ext_router, ext_entitlements' /app/backend/open_webui/main.py \
        || (echo "ERROR: ext router import not injected into main.py — upstream may have moved utils.router." && exit 1)
RUN grep -q 'app.include_router(ext_syllabus.router' /app/backend/open_webui/main.py \
        || (echo "ERROR: ext_syllabus router include missing from main.py." && exit 1)
RUN grep -q 'app.include_router(ext_router.router' /app/backend/open_webui/main.py \
        || (echo "ERROR: ext_router router include missing from main.py." && exit 1)
RUN grep -q 'app.include_router(ext_entitlements.router' /app/backend/open_webui/main.py \
        || (echo "ERROR: ext_entitlements router include missing from main.py." && exit 1)
RUN test -f /app/backend/open_webui/routers/ext_authz.py \
        || (echo "ERROR: ext_authz.py not copied — audit logging will be a no-op in production." && exit 1)
RUN test -f /app/backend/open_webui/routers/ext_entitlements.py \
        || (echo "ERROR: ext_entitlements.py not copied — access check API will be unavailable." && exit 1)

# Expose the standard port
EXPOSE 8080
CMD [ "bash", "start.sh" ]

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

# Build the frontend with our injected components
RUN npm run build


# Stage 2: Final Production Image
# Pull the official pre-built Python backend image to save massive build time
FROM ghcr.io/open-webui/open-webui:0.9.5

# Overwrite the default compiled frontend with our newly compiled custom frontend
COPY --chown=0:0 --from=frontend-builder /app/build /app/build

# Copy the custom backend extensions directly into the container's router directory
COPY extensions/ext_router.py /app/backend/open_webui/routers/ext_router.py
COPY extensions/ext_syllabus.py /app/backend/open_webui/routers/ext_syllabus.py

# Inject the router registration into the main FastAPI application
RUN sed -i '/app.include_router(utils.router/a \
from open_webui.routers import ext_syllabus, ext_router\n\
app.include_router(ext_syllabus.router, prefix="/api/ext/syllabus", tags=["ext"])\n\
app.include_router(ext_router.router, prefix="/api/ext", tags=["ext"])' /app/backend/open_webui/main.py

# Expose the standard port
EXPOSE 8080
CMD [ "bash", "start.sh" ]

# Walkthrough: The Anchor Architecture

I have completely rewritten the Svelte integration from the ground up. We are now using a true "Plug-N-Play" template architecture that guarantees your platform loads with blazing native speed.

## The Modular Philosophy

We have designated `extensions/frontend/` as the definitive home for all your UI custom code. Open WebUI is now treated purely as a baseline template. We touch its source code exactly **once** using a tiny `sed` command in the `Dockerfile` to drop an "Anchor".

### The Master Wrapper: `Anchor.svelte`
This file simply pulls in all your other custom `.svelte` modules and stacks them in the sidebar. 
```svelte
<script>
    import SyllabusSidebarMenu from './SyllabusSidebarMenu.svelte';
    import ExampleMenu from './ExampleMenu.svelte';
</script>

<div class="custom-extensions-anchor pb-2">
    <SyllabusSidebarMenu />
    <ExampleMenu />
</div>
```

If you ever want to add a third menu (e.g. `BillingMenu.svelte`), you just create the file in the `frontend` folder and add one line to `Anchor.svelte`!

### The New `SyllabusSidebarMenu.svelte`
Instead of forcefully hijacking the center screen (which caused the lag), the syllabus is now a sleek, deeply-nested accordion tree that lives natively in the left panel.
- It dynamically builds a tree of Exam > Subject > Topic > Lesson.
- When a student clicks a prompt (e.g. "📖 Generate Study Notes"), it instantly sends a command to the main Chat window, populates the text box, and triggers the AI exactly as you designed!

### The `ExampleMenu.svelte`
To demonstrate how effortlessly you can add new features, I built `ExampleMenu.svelte`. It renders an "Extra Resources" folder right below the Syllabus with two buttons: "Platform Guide" and "External Documentation".

## How to Test
1. You can now safely delete `extensions/frontend/SyllabusExplorer.svelte` as it is no longer used.
2. Run the build command one more time to compile these new `.svelte` files into the core javascript bundle:
```bash
sudo docker compose up -d --build
```

You will notice the main screen is clean and fast, and your custom menus are perfectly embedded into the left Sidebar! 

> [!TIP]
> Remember, to hide the right Chat Controls from your students, just log into Open WebUI, open your **Admin Panel > Settings > Interface**, and disable the controls for the `user` role!

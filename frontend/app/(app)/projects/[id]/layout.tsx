import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import ProjectTabs from "@/components/projects/ProjectTabs";

export default async function ProjectLayout({
  children,
  params,
}: LayoutProps<"/projects/[id]">) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: project } = await supabase
    .from("projects")
    .select("id, name, color")
    .eq("id", id)
    .single();

  if (!project) redirect("/projects");

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-bg-root text-text-primary">
      <header className="shrink-0 flex items-center justify-between gap-3 px-4 h-12 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm">
        <div className="flex items-center gap-2 min-w-0">
          <span
            className="w-3 h-3 rounded-full shrink-0"
            style={{ backgroundColor: project.color }}
          />
          <h1 className="text-sm font-semibold truncate">{project.name}</h1>
        </div>
        <ProjectTabs projectId={project.id} />
      </header>

      <div className="flex flex-col flex-1 min-h-0">{children}</div>
    </main>
  );
}

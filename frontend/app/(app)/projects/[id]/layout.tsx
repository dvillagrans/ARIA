import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import ProjectTabs from "@/components/projects/ProjectTabs";
import ProjectSplitLayout from "@/components/projects/ProjectSplitLayout";

export default async function ProjectLayout({
  children,
  params,
}: LayoutProps<"/projects/[id]">) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: project } = await supabase
    .from("projects")
    .select("id, name, color, context, github_repo")
    .eq("id", id)
    .single();

  if (!project) redirect("/projects");

  return (
    <main className="flex flex-col flex-1 min-h-0 bg-bg-root text-text-primary">
      <header className="shrink-0 border-b border-bg-elevated bg-bg-surface/50 backdrop-blur-sm pt-safe">
        <div className="flex items-center justify-between gap-3 px-4 h-12">
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="w-3 h-3 rounded-full shrink-0"
              style={{ backgroundColor: project.color }}
            />
            <h1 className="text-sm font-semibold truncate">{project.name}</h1>
          </div>
          <div className="lg:hidden">
            <ProjectTabs projectId={project.id} />
          </div>
        </div>
      </header>

      <ProjectSplitLayout
        projectId={project.id}
        projectName={project.name}
        projectColor={project.color}
        projectContext={(project as Record<string, unknown>).context as string | null ?? null}
        projectGithubRepo={(project as Record<string, unknown>).github_repo as string | null ?? null}
      >
        {children}
      </ProjectSplitLayout>
    </main>
  );
}

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import ProjectInfoEditor, {
  type ProjectLink,
} from "@/components/projects/ProjectInfoEditor";

export default async function ProjectInfoPage({
  params,
}: PageProps<"/projects/[id]/info">) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: project } = await supabase
    .from("projects")
    .select("id, links, context, github_repo")
    .eq("id", id)
    .single();

  if (!project) redirect("/projects");

  const links: ProjectLink[] = Array.isArray(project.links)
    ? (project.links as ProjectLink[])
    : [];

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-6 scrollbar-thin">
      <ProjectInfoEditor
        projectId={project.id}
        initialLinks={links}
        initialNotes={project.context ?? ""}
        initialGithubRepo={project.github_repo ?? ""}
      />
    </div>
  );
}

import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";
import ChatView from "@/components/chat/ChatView";

interface Props {
  params: Promise<{ id: string }>;
}

export default async function ProjectChatPage({ params }: Props) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: project } = await supabase
    .from("projects")
    .select("id, name, color")
    .eq("id", id)
    .single();

  if (!project) redirect("/projects");

  return (
    <ChatView
      projectId={project.id}
      projectName={project.name}
      projectColor={project.color}
    />
  );
}

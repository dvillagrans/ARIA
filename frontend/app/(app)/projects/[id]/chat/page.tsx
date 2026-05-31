import ChatView from "@/components/chat/ChatView";

// The [id] layout fetches the project, validates existence, and renders the
// header + tabs — so this page only needs the id and hides ChatView's header.
export default async function ProjectChatPage({
  params,
}: PageProps<"/projects/[id]/chat">) {
  const { id } = await params;
  return <ChatView projectId={id} hideHeader />;
}

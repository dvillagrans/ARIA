"use client";

import type { Components } from "react-markdown";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const components: Components = {
  h2: ({ children }) => (
    <h2 className="mt-5 mb-2 text-[14px] font-semibold text-accent tracking-wide first:mt-0">
      {children}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-4 mb-1.5 text-[13px] font-semibold text-text-primary">
      {children}
    </h3>
  ),
  p: ({ children }) => (
    <p className="mb-3 text-[13px] leading-relaxed text-text-primary last:mb-0">
      {children}
    </p>
  ),
  ul: ({ children }) => (
    <ul className="mb-3 ml-4 list-disc space-y-1.5 text-[13px] text-text-primary">
      {children}
    </ul>
  ),
  ol: ({ children }) => (
    <ol className="mb-3 ml-4 list-decimal space-y-1.5 text-[13px] text-text-primary">
      {children}
    </ol>
  ),
  li: ({ children }) => <li className="leading-relaxed">{children}</li>,
  strong: ({ children }) => (
    <strong className="font-semibold text-text-primary">{children}</strong>
  ),
  em: ({ children }) => <em className="italic text-text-secondary">{children}</em>,
  a: ({ href, children }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent underline underline-offset-2 hover:text-accent-hover"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-3 border-l-2 border-accent/40 pl-3 text-text-secondary">
      {children}
    </blockquote>
  ),
  hr: () => <hr className="my-4 border-border-subtle" />,
  table: ({ children }) => (
    <div className="mb-4 overflow-x-auto rounded-sm border border-border-subtle">
      <table className="w-full min-w-[280px] border-collapse text-left text-[12px]">
        {children}
      </table>
    </div>
  ),
  thead: ({ children }) => (
    <thead className="bg-bg-surface text-text-secondary">{children}</thead>
  ),
  tbody: ({ children }) => <tbody className="divide-y divide-border-subtle">{children}</tbody>,
  tr: ({ children }) => <tr className="hover:bg-bg-surface/50">{children}</tr>,
  th: ({ children }) => (
    <th className="px-3 py-2 font-semibold text-accent">{children}</th>
  ),
  td: ({ children }) => (
    <td className="px-3 py-2 text-text-primary align-top">{children}</td>
  ),
  code: ({ className, children }) => {
    const isBlock = className?.includes("language-");
    if (isBlock) {
      return (
        <pre className="mb-3 overflow-x-auto rounded-sm border border-border-subtle bg-bg-surface p-3 text-[12px]">
          <code>{children}</code>
        </pre>
      );
    }
    return (
      <code className="rounded-sm bg-bg-surface px-1 py-0.5 text-[12px] text-accent">
        {children}
      </code>
    );
  },
};

interface MarkdownMessageProps {
  content: string;
  isStreaming?: boolean;
}

export default function MarkdownMessage({ content, isStreaming }: MarkdownMessageProps) {
  return (
    <div className="markdown-message max-w-none break-words">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
      {isStreaming && <span className="cursor-blink">█</span>}
    </div>
  );
}

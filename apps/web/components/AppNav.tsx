"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clock3, Files, Inbox } from "lucide-react";

const NAV_ITEMS = [
  { href: "/", label: "上传", icon: Inbox },
  { href: "/jobs", label: "任务", icon: Files },
  { href: "/history", label: "历史", icon: Clock3 },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="nav">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

        return (
          <Link className={active ? "active" : ""} href={item.href} key={item.href}>
            <Icon size={15} />
            <span>{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}

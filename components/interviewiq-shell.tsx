'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import {
  BarChart3,
  BookOpenCheck,
  ChevronDown,
  CircleHelp,
  FileText,
  LayoutDashboard,
  Menu,
  Mic2,
  Settings,
  Sparkles,
  UserRound,
  X,
} from 'lucide-react'

export type AppView = 'overview' | 'interview'

const primaryNavigation = [
  { label: 'Overview', icon: LayoutDashboard, view: 'overview' as AppView },
  { label: 'Start interview', icon: Mic2, view: 'interview' as AppView },
  { label: 'Interview history', icon: FileText, view: null },
]

const intelligenceNavigation = [
  { label: 'Communication coach', icon: Sparkles },
  { label: 'Skill gap analysis', icon: BookOpenCheck },
  { label: 'Reports', icon: BarChart3 },
]

export function InterviewIQShell({ children }: { children: React.ReactNode }) {
  const [view, setView] = useState<AppView>('overview')
  const [mobileOpen, setMobileOpen] = useState(false)

  return (
    <div className="min-h-screen bg-background text-foreground">
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-border bg-sidebar px-4 py-5 transition-transform duration-200 lg:translate-x-0',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex items-center justify-between px-3">
          <button className="flex items-center gap-2.5 text-left" onClick={() => { setView('overview'); setMobileOpen(false) }} aria-label="Go to overview">
            <span className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground">
              <span className="text-sm font-semibold tracking-tight">IQ</span>
            </span>
            <span className="font-semibold tracking-[-0.03em]">InterviewIQ</span>
          </button>
          <button className="rounded-md p-1.5 text-muted-foreground hover:bg-accent lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation">
            <X className="size-4" />
          </button>
        </div>

        <nav className="mt-10 flex flex-1 flex-col gap-8" aria-label="Main navigation">
          <div>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Workspace</p>
            <div className="flex flex-col gap-1">
              {primaryNavigation.map(({ label, icon: Icon, view: target }) => (
                <button
                  key={label}
                  disabled={!target}
                  onClick={() => { if (target) { setView(target); setMobileOpen(false) } }}
                  className={cn(
                    'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm transition-colors',
                    target ? 'text-sidebar-foreground hover:bg-sidebar-accent' : 'cursor-not-allowed text-muted-foreground/60',
                    view === target && 'bg-sidebar-accent font-medium text-sidebar-primary',
                  )}
                >
                  <Icon className="size-[17px]" strokeWidth={1.8} />
                  {label}
                  {!target && <span className="ml-auto text-[10px] uppercase tracking-wider text-muted-foreground/60">Soon</span>}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">Intelligence</p>
            <div className="flex flex-col gap-1">
              {intelligenceNavigation.map(({ label, icon: Icon }) => (
                <button key={label} disabled className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2.5 text-sm text-muted-foreground/60">
                  <Icon className="size-[17px]" strokeWidth={1.8} />
                  {label}
                  <span className="ml-auto text-[10px] uppercase tracking-wider text-muted-foreground/60">Soon</span>
                </button>
              ))}
            </div>
          </div>
        </nav>

        <div className="flex flex-col gap-1 border-t border-border pt-4">
          <button disabled className="flex cursor-not-allowed items-center gap-3 rounded-md px-3 py-2.5 text-sm text-muted-foreground/60"><Settings className="size-[17px]" strokeWidth={1.8} />Settings<span className="ml-auto text-[10px] uppercase tracking-wider">Soon</span></button>
          <div className="mt-3 flex items-center gap-3 rounded-md bg-sidebar-accent/60 px-3 py-3">
            <span className="flex size-8 items-center justify-center rounded-full bg-[#d9cfc0] text-xs font-semibold text-foreground">JD</span>
            <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">Jordan Davis</p><p className="truncate text-xs text-muted-foreground">Candidate account</p></div>
            <ChevronDown className="size-4 text-muted-foreground" />
          </div>
        </div>
      </aside>

      {mobileOpen && <button className="fixed inset-0 z-30 bg-foreground/15 lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" />}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-border bg-background/95 px-5 backdrop-blur-sm sm:px-8">
          <div className="flex items-center gap-3"><button className="rounded-md p-2 hover:bg-accent lg:hidden" onClick={() => setMobileOpen(true)} aria-label="Open navigation"><Menu className="size-5" /></button><span className="text-sm text-muted-foreground">Candidate workspace</span></div>
          <div className="flex items-center gap-4"><button className="hidden items-center gap-2 text-xs text-muted-foreground transition-colors hover:text-foreground sm:flex"><CircleHelp className="size-4" />Help center</button><span className="flex size-8 items-center justify-center rounded-full border border-border bg-card text-xs font-semibold">JD</span></div>
        </header>
        <main>{children({ view, setView })}</main>
      </div>
    </div>
  )
}

export function MobileUserIcon() { return <UserRound className="size-4" /> }

export { primaryNavigation }
export type ShellChildren = { view: AppView; setView: (view: AppView) => void }

export default InterviewIQShell

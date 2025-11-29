import { NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  ListTodo,
  Film,
  Music,
  Settings,
  Cpu
} from 'lucide-react'
import { clsx } from 'clsx'

const navigation = [
  { name: '仪表盘', href: '/dashboard', icon: LayoutDashboard },
  { name: '任务管理', href: '/tasks', icon: ListTodo },
  { name: '视频库', href: '/assets/videos', icon: Film },
  { name: '音频库', href: '/assets/audios', icon: Music },
  { name: '系统配置', href: '/settings', icon: Settings },
  { name: '检索后端', href: '/settings/retriever', icon: Cpu },
]

export default function Sidebar() {
  return (
    <div className="fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-gray-200">
      <div className="flex h-16 items-center gap-2 px-6 border-b border-gray-200">
        <Film className="h-8 w-8 text-primary-600" />
        <span className="text-xl font-bold text-gray-900">Song2Video</span>
      </div>
      <nav className="flex flex-1 flex-col p-4">
        <ul className="space-y-1">
          {navigation.map((item) => (
            <li key={item.name}>
              <NavLink
                to={item.href}
                className={({ isActive }) =>
                  clsx(
                    'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-primary-50 text-primary-700'
                      : 'text-gray-700 hover:bg-gray-100 hover:text-gray-900'
                  )
                }
              >
                <item.icon className="h-5 w-5 shrink-0" />
                {item.name}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  )
}

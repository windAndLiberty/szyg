export default function Footer() {
  return (
    <footer className="ml-[260px] px-8 py-4 border-t border-[#1E293B] bg-[#0B0F1A]">
      <div className="flex items-center justify-between text-xs text-[#64748B]">
        <span>DealFlow v1.0.0</span>
        <span>&copy; {new Date().getFullYear()} DealFlow. All rights reserved.</span>
      </div>
    </footer>
  )
}

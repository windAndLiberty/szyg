import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:ring-2 focus-visible:ring-[#6366F1]/50",
  {
    variants: {
      variant: {
        default: "bg-[#6366F1] text-white hover:bg-[#818CF8] active:scale-[0.97]",
        destructive: "bg-[#EF4444] text-white hover:bg-[#EF4444]/90",
        outline: "border border-[#1E293B] bg-transparent text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9] hover:border-[#334155]",
        secondary: "bg-[#1A2235] text-[#F1F5F9] hover:bg-[#334155]",
        ghost: "text-[#94A3B8] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#F1F5F9]",
        link: "text-[#6366F1] underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 rounded-md gap-1.5 px-3",
        lg: "h-10 rounded-md px-6",
        icon: "size-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }

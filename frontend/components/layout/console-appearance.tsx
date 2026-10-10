"use client";

import { applyDensity, applyMode, Density, Mode } from "@cloudscape-design/global-styles";
import { applyTheme, type Theme } from "@cloudscape-design/components/theming";
import { useLayoutEffect, type ReactNode } from "react";

// Only brand actions are themed. Cloudscape owns the dark
// palette, contrast states, density, focus rings, and every component surface.
const consoleTheme: Theme = {
  tokens: {
    colorBackgroundButtonPrimaryDefault: "{colorAmber400}",
    colorBackgroundButtonPrimaryHover: "{colorAmber500}",
    colorBackgroundButtonPrimaryActive: "{colorAmber500}",
    colorBorderButtonPrimaryDefault: "{colorAmber400}",
    colorBorderButtonPrimaryHover: "{colorAmber500}",
    colorBorderButtonPrimaryActive: "{colorAmber500}",
    colorTextButtonPrimaryDefault: "{colorGrey950}",
    colorTextButtonPrimaryHover: "{colorGrey950}",
    colorTextButtonPrimaryActive: "{colorGrey950}",
  },
};

export function ConsoleAppearance({ children }: { children: ReactNode }) {
  useLayoutEffect(() => {
    applyMode(Mode.Dark);
    applyDensity(Density.Compact);
    const { reset } = applyTheme({ theme: consoleTheme, selector: "body" });
    return reset;
  }, []);

  return children;
}

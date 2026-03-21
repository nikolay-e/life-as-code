import { createContext, useContext, useState } from "react";

const DateContext = createContext<Date>(new Date());

export function useDateProviderValue(): Date {
  const [today] = useState(() => new Date());
  return today;
}

export const DateProvider = DateContext.Provider;

export function useToday(): Date {
  return useContext(DateContext);
}

//+------------------------------------------------------------------+
//|                                   TradeGuard_PropProtector.mq5   |
//|                     گارد محافظ دراودان روزانه پراپ — تریدگارد     |
//|         محاسبه حجم امن + بستن خودکار معاملات قبل از سوختن چالش    |
//+------------------------------------------------------------------+
#property copyright "TradeGuard Pro Mini-App"
#property version   "1.20"
#property strict

#include <Trade\Trade.mqh>
CTrade trade;

//--- ورودی‌های قابل تنظیم توسط تریدر
input double InpInitialBalance     = 10000.0; // سایز اولیه حساب پراپ ($)
input double InpPropDailyLimitPct  = 5.0;     // سقف دراودان روزانه پراپ (درصد)
input double InpGuardCutPct        = 3.8;     // سقف قفل خودکار تریدگارد (درصد - قبل از خط قرمز پراپ)
input double InpRiskPerTradePct    = 0.5;     // ریسک پیشنهادی هر معامله (درصد)
input int    InpDefaultSLPoints    = 500;     // حد ضرر پیش‌فرض به پوینت (۵۰۰ پوینت = ۵۰ پیپ)
input bool   InpAutoClosePositions = true;    // بستن خودکار تمام پوزیشن‌ها در لحظه برخورد به گارد

//--- متغیرهای داخلی روزانه
datetime g_currentDayStart = 0;
double   g_dayStartAnchor  = 0.0;
bool     g_lockedToday     = false;

//+------------------------------------------------------------------+
//| مقداردهی اولیه اکسپرت                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   ResetDailyAnchorIfNeeded();
   EventSetTimer(1);
   UpdateHUD();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| پاکسازی اشیای روی چارت                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   ObjectsDeleteAll(0, "TG_HUD_");
}

//+------------------------------------------------------------------+
//| بررسی لحظه‌ای در هر تیک و هر ثانیه                               |
//+------------------------------------------------------------------+
void OnTick()
{
   CheckGuard();
}

void OnTimer()
{
   CheckGuard();
}

//+------------------------------------------------------------------+
//| ریست مبنای دراودان در شروع روز جدید سرور بروکر                   |
//+------------------------------------------------------------------+
void ResetDailyAnchorIfNeeded()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   dt.hour = 0;
   dt.min  = 0;
   dt.sec  = 0;
   datetime todayStart = StructToTime(dt);

   if(todayStart != g_currentDayStart)
   {
      g_currentDayStart = todayStart;
      // اکثر پراپ‌فرم‌ها مبنای دراودان روزانه را بالاترین مقدار بین Balance و Equity اول روز می‌گیرند
      double bal = AccountInfoDouble(ACCOUNT_BALANCE);
      double eq  = AccountInfoDouble(ACCOUNT_EQUITY);
      g_dayStartAnchor = MathMax(bal, eq);
      g_lockedToday    = false;
   }
}

//+------------------------------------------------------------------+
//| هسته اصلی محافظت از حساب پراپ                                     |
//+------------------------------------------------------------------+
void CheckGuard()
{
   ResetDailyAnchorIfNeeded();

   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double baseAmount = (InpInitialBalance > 0.0) ? InpInitialBalance : g_dayStartAnchor;
   double guardCash  = baseAmount * (InpGuardCutPct / 100.0);
   double floorEq    = g_dayStartAnchor - guardCash;

   // اگر اکوئیتی به خط قرمز تریدگارد رسید یا در وضعیت قفل امروز هستیم
   if(equity <= floorEq || g_lockedToday)
   {
      if(!g_lockedToday)
      {
         g_lockedToday = true;
         Alert("🛡️ TradeGuard: سقف ضرر روزانه گارد فعال شد! در حال بستن معاملات برای نجات چالش پراپ...");
      }

      if(InpAutoClosePositions)
      {
         CloseAllPositionsAndOrders();
      }
   }

   UpdateHUD();
}

//+------------------------------------------------------------------+
//| بستن فوری تمام پوزیشن‌های باز و سفارش‌های شرطی                   |
//+------------------------------------------------------------------+
void CloseAllPositionsAndOrders()
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0)
         trade.PositionClose(ticket);
   }

   for(int j = OrdersTotal() - 1; j >= 0; j--)
   {
      ulong orderTicket = OrderGetTicket(j);
      if(orderTicket > 0)
         trade.OrderDelete(orderTicket);
   }
}

//+------------------------------------------------------------------+
//| محاسبه حجم امن پیشنهادی بر اساس ارزش تیک نماد فعلی               |
//+------------------------------------------------------------------+
double CalcSafeLot()
{
   double baseAmount = (InpInitialBalance > 0.0) ? InpInitialBalance : g_dayStartAnchor;
   double riskCash   = baseAmount * (InpRiskPerTradePct / 100.0);
   double tickVal    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double pointVal   = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   if(tickVal <= 0 || tickSize <= 0 || pointVal <= 0 || InpDefaultSLPoints <= 0)
      return 0.01;

   double valuePerPointPerLot = tickVal * (pointVal / tickSize);
   if(valuePerPointPerLot <= 0)
      return 0.01;

   double rawLot  = riskCash / (InpDefaultSLPoints * valuePerPointPerLot);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

   if(stepLot > 0)
      rawLot = MathFloor(rawLot / stepLot) * stepLot;

   return MathMax(minLot, NormalizeDouble(rawLot, 2));
}

//+------------------------------------------------------------------+
//| نمایش پنل وضعیت زنده روی چارت متاتریدر                            |
//+------------------------------------------------------------------+
void DrawLabel(string name, int x, int y, string text, color clr, int fontSize = 10)
{
   if(ObjectFind(0, name) < 0)
   {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetString(0, name, OBJPROP_FONT, "Tahoma");
   }
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, fontSize);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
}

void UpdateHUD()
{
   double equity     = AccountInfoDouble(ACCOUNT_EQUITY);
   double baseAmount = (InpInitialBalance > 0.0) ? InpInitialBalance : g_dayStartAnchor;
   double guardCash  = baseAmount * (InpGuardCutPct / 100.0);
   double usedLoss   = MathMax(0.0, g_dayStartAnchor - equity);
   double remainCash = MathMax(0.0, guardCash - usedLoss);
   double safeLot    = CalcSafeLot();

   color statusClr = g_lockedToday ? clrCrimson : (remainCash < guardCash * 0.35 ? clrOrange : clrMediumSpringGreen);
   string statusTxt = g_lockedToday ? "LOCKED TODAY (حساب محافظت شد)" : "ACTIVE GUARD (محافظ فعال)";

   DrawLabel("TG_HUD_1", 18, 24, "=== TradeGuard Prop Protector ===", clrAqua, 10);
   DrawLabel("TG_HUD_2", 18, 44, "Status: " + statusTxt, statusClr, 10);
   DrawLabel("TG_HUD_3", 18, 64, StringFormat("Day Anchor: $%.2f | Equity: $%.2f", g_dayStartAnchor, equity), clrWhite, 9);
   DrawLabel("TG_HUD_4", 18, 82, StringFormat("Remaining Guard Buffer: $%.2f (Cut at %.1f%%)", remainCash, InpGuardCutPct), statusClr, 9);
   DrawLabel("TG_HUD_5", 18, 100, StringFormat("Suggested Safe Lot (%.1f%% Risk): %.2f Lot", InpRiskPerTradePct, safeLot), clrGold, 9);
}
//+------------------------------------------------------------------+

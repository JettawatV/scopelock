from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas

OUT = "artifacts/scopelock-architecture-diagram.pdf"
W, H = landscape(A4)
c = canvas.Canvas(OUT, pagesize=(W, H))
c.setTitle("ScopeLock Architecture Diagram")
c.setFillColor(colors.HexColor("#F8FAFC")); c.rect(0, 0, W, H, fill=1, stroke=0)
c.setFillColor(colors.HexColor("#0F172A")); c.setFont("Helvetica-Bold", 24)
c.drawString(34, H-42, "ScopeLock architecture")
c.setFillColor(colors.HexColor("#64748B")); c.setFont("Helvetica", 10)
c.drawString(36, H-59, "Event-driven proposal automation with approval-gated commercial communication")

def box(x, y, w, h, title, lines, fill="#FFFFFF", accent="#111827"):
    c.setFillColor(colors.HexColor(fill)); c.setStrokeColor(colors.HexColor("#CBD5E1")); c.roundRect(x,y,w,h,10,fill=1,stroke=1)
    c.setFillColor(colors.HexColor(accent)); c.setFont("Helvetica-Bold", 11); c.drawString(x+12,y+h-21,title)
    c.setFillColor(colors.HexColor("#475569")); c.setFont("Helvetica", 8.5)
    for i,line in enumerate(lines): c.drawString(x+12,y+h-37-(i*13),line)

def arrow(x1,y1,x2,y2,label=None):
    c.setStrokeColor(colors.HexColor("#64748B")); c.setFillColor(colors.HexColor("#64748B")); c.setLineWidth(1.4)
    c.line(x1,y1,x2,y2)
    import math
    a=math.atan2(y2-y1,x2-x1); size=6
    c.line(x2,y2,x2-size*math.cos(a-0.5),y2-size*math.sin(a-0.5)); c.line(x2,y2,x2-size*math.cos(a+0.5),y2-size*math.sin(a+0.5))
    if label:
        c.setFont("Helvetica",7.5); c.setFillColor(colors.HexColor("#64748B")); c.drawCentredString((x1+x2)/2,(y1+y2)/2+5,label)

box(34, 300, 130, 90, "Client", ["Gmail mailbox", "Project requirements", "Scope change replies"])
box(205, 300, 130, 90, "Gmail API", ["users.watch", "History API", "Thread + message reads"])
box(376, 300, 130, 90, "Cloud Pub/Sub", ["Gmail push event", "Authenticated delivery", "Retry-safe message ID"] , fill="#EEF2FF", accent="#4338CA")
box(547, 270, 170, 150, "Cloud Run · ScopeLock API", ["FastAPI application", "Webhook + command endpoints", "Idempotency + state machine", "Private service"] , fill="#ECFDF5", accent="#047857")
box(748, 348, 125, 92, "Google ADK", ["Requirement analyzer", "Scope-change analyzer", "Structured outputs"], fill="#FFF7ED", accent="#C2410C")
box(748, 230, 125, 92, "Gemini 3.5 Flash", ["Intent understanding", "Evidence extraction", "SOP module selection"], fill="#FFF7ED", accent="#C2410C")
box(547, 92, 170, 125, "Deterministic commerce", ["SOP pricing rules", "Timeline calculation", "Delta + revisions", "Approval policy"] , fill="#F1F5F9", accent="#0F172A")
box(748, 92, 125, 110, "Firestore", ["Projects + scopes", "Proposal versions", "Approvals + sends", "Audit records"], fill="#EFF6FF", accent="#1D4ED8")
box(900, 300, 135, 110, "Reviewer gateway", ["Cloud Run", "Firebase Auth", "Public HTTPS UI"], fill="#F5F3FF", accent="#6D28D9")
box(900, 120, 135, 110, "Operator dashboard", ["Review proposal", "Edit email draft", "Approve / send", "See scope impact"], fill="#FFFFFF", accent="#111827")
box(1060, 300, 130, 110, "Gmail send", ["Draft creation", "Approval-gated send", "Same thread reply"])

arrow(164,345,205,345,"email")
arrow(335,345,376,345,"push")
arrow(506,345,547,345,"webhook")
arrow(717,382,748,395,"invoke")
arrow(810,348,810,322,"model")
arrow(717,300,717,217,"calculate")
arrow(717,155,748,155,"persist")
arrow(873,395,900,370,"result")
arrow(965,300,965,230,"review")
arrow(1035,355,1060,355,"approved")
arrow(1060,330,1035,175,"reply")
arrow(873,155,900,175,"state")

c.setFillColor(colors.HexColor("#475569")); c.setFont("Helvetica", 8)
c.drawString(36, 32, "Human approval is required before any proposal or commercial scope revision is sent.")
c.save()

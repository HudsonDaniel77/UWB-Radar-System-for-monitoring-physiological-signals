from docx import Document

doc = Document('Sleep_Detection_Project_Report.docx')

# Find INTRODUCTION and OBJECTIVES headings
intro_idx = None
objectives_idx = None

for i, para in enumerate(doc.paragraphs):
    if 'INTRODUCTION' in para.text and para.style.name == 'Heading 1':
        intro_idx = i
    if intro_idx is not None and i > intro_idx and 'OBJECTIVES' in para.text and para.style.name == 'Heading 1':
        objectives_idx = i
        break

print(f"INTRODUCTION at index: {intro_idx}")
print(f"OBJECTIVES at index: {objectives_idx}")

# Remove all content between INTRODUCTION and OBJECTIVES
if intro_idx is not None and objectives_idx is not None:
    for i in range(objectives_idx - 1, intro_idx, -1):
        p = doc.paragraphs[i]._element
        p.getparent().remove(p)
    print(f"Removed {objectives_idx - intro_idx - 1} paragraphs")

# Rebuild the document from scratch to ensure proper structure
doc2 = Document('Sleep_Detection_Project_Report.docx')

# Find INTRODUCTION again
intro_idx = None
for i, para in enumerate(doc2.paragraphs):
    if 'INTRODUCTION' in para.text and para.style.name == 'Heading 1':
        intro_idx = i
        break

print(f"INTRODUCTION now at index: {intro_idx}")

# Get the insertion point element
intro_para = doc2.paragraphs[intro_idx]

# Insert new paragraphs after INTRODUCTION
insert_point = intro_para._element

# Intro paragraph 1
p1 = doc2.add_paragraph("Modern healthcare systems increasingly recognize sleep monitoring as critical for diagnosing and managing sleep-related respiratory and neurological disorders. Obstructive Sleep Apnea (OSA) affects roughly 2.9% of children and up to 37% of adults worldwide, with significant economic implications—annual OSA-related healthcare costs exceed $150 billion globally, including indirect costs from productivity loss and increased accident rates.")
insert_point.addnext(p1._element)

# Intro paragraph 2
p2 = doc2.add_paragraph("Sleep-related physiological disturbances caused by obstructive sleep apnea, periodic breathing, and other sleep disorders require precise detection and staging to guide clinical interventions. Accurate sleep stage classification remains essential for diagnosing disorders and monitoring treatment efficacy.")
p1._element.addnext(p2._element)

# Blank line
blank1 = doc2.add_paragraph("")
p2._element.addnext(blank1._element)

# Limitations heading
lim_head = doc2.add_paragraph("Limitations of Existing Methods:")
lim_head.style = 'Normal'
blank1._element.addnext(lim_head._element)

# Limitation bullets
limitations = [
    "Manual sleep staging requires certified sleep specialists, creating significant delays and high diagnostic costs",
    "Contact-based sensors (electrodes, chest belts, actigraphy) cause discomfort, sleep disruption, and data artifacts",
    "Wearable devices provide only fragmented vital signs without comprehensive sleep architecture information",
    "Most AI-based solutions are limited to heart rate or respiration alone, failing to capture the full physiological picture"
]

current = lim_head._element
for bullet_text in limitations:
    bullet = doc2.add_paragraph(bullet_text, style='List Bullet')
    current.addnext(bullet._element)
    current = bullet._element

# Blank line
blank2 = doc2.add_paragraph("")
current.addnext(blank2._element)
current = blank2._element

# Proposed Solution heading
sol_head = doc2.add_paragraph("Proposed Solution:")
sol_head.style = 'Normal'
current.addnext(sol_head._element)
current = sol_head._element

# Solution intro
sol_intro = doc2.add_paragraph("This project introduces a novel AI-powered non-contact sleep monitoring system that:")
sol_intro.style = 'Normal'
current.addnext(sol_intro._element)
current = sol_intro._element

# Solution bullets
proposed = [
    "Detects and classifies sleep into four clinically relevant stages (Wake, REM, Light, Deep) with sensitivity > 82% and specificity > 79%",
    "Uses physiological-specific optimized models combining rule-based classifiers with Random Forest, SVM, and deep learning (LSTM, CNN-LSTM, TCN)",
    "Supports real-time inference < 50 ms per 30-second epoch for continuous monitoring applications",
    "Includes complete deployment pipeline (Flask REST API + React web dashboard) enabling seamless integration",
    "Enables continuous non-contact home-based and clinical monitoring without subject discomfort or sensor artifacts"
]

for bullet_text in proposed:
    bullet = doc2.add_paragraph(bullet_text, style='List Bullet')
    current.addnext(bullet._element)
    current = bullet._element

doc2.save('Sleep_Detection_Project_Report.docx')
print('✓ Document fixed successfully')
print('✓ INTRODUCTION section properly formatted')

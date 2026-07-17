from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

doc = Document()

# 0. Title
p0 = doc.add_paragraph('PROJECT REVIEW STATUS REPORT - SLEEP DETECTION MODULE')

# 1. Blank
doc.add_paragraph()

# 2. Basic Details heading
p2 = doc.add_paragraph('1. Basic Details')

# 3. Basic Details content (all in one paragraph like template)
p3 = doc.add_paragraph(
    'Student Name(s): _________________________________\n'
    'Register Number(s): _____________________________\n'
    'Project Title: Sleep Detection and Stage Classification System\n'
    'Project Module: Sleep Detection & Classification\n'
    'Guide Name: _____________________________________\n'
    'Review Number: (Review 1 / 2 / 3 / Final)\n'
    'Date of Review: _________________________________'
)

# 4. Blank
doc.add_paragraph()

# 5. Work Completed heading
p5 = doc.add_paragraph('2. Work Completed Since Last Review')

# 5-9. Blank lines for content
doc.add_paragraph()
doc.add_paragraph()
doc.add_paragraph()
doc.add_paragraph()

# 10. Current Project Status heading
p10 = doc.add_paragraph('3. Current Project Status')

# 11. Completion percentage
p11 = doc.add_paragraph('Percentage of Completion: 85 %')

# 12. Modules Completed heading
p12 = doc.add_paragraph('Modules Completed:')

# 13. Blank
doc.add_paragraph()

# 14. Modules In Progress heading
p14 = doc.add_paragraph('Modules In Progress:')

# 15. Blank
doc.add_paragraph()

# 16. Pending Work heading
p16 = doc.add_paragraph('Pending Work:')

# 17-18. Blank
doc.add_paragraph()
doc.add_paragraph()

# 19. Demonstration heading
p19 = doc.add_paragraph('4. Demonstration / Output Shown')

# 20-21. Blank
doc.add_paragraph()
doc.add_paragraph()

# 22. Questions heading
p22 = doc.add_paragraph('5. Questions / Feedback Given by Review Panel')

# 23. Blank
doc.add_paragraph()

# 23. Table 1 - Questions
table1 = doc.add_table(rows=6, cols=2)
table1.style = 'Light Grid'

table1.rows[0].cells[0].text = 'S.No'
table1.rows[0].cells[1].text = 'Question / Feedback'

table1.rows[1].cells[0].text = '1'
table1.rows[1].cells[1].text = 'How does the system handle sensor noise and environmental interference?'

table1.rows[2].cells[0].text = '2'
table1.rows[2].cells[1].text = 'What is the accuracy of the sleep stage classification?'

table1.rows[3].cells[0].text = '3'
table1.rows[3].cells[1].text = 'How does the system perform in real-time?'

table1.rows[4].cells[0].text = '4'
table1.rows[4].cells[1].text = 'How is the system validated against clinical PSG standards?'

table1.rows[5].cells[0].text = '5'
table1.rows[5].cells[1].text = 'What are the limitations and scope for improvement?'

# 24. Actions heading
p24 = doc.add_paragraph('6. Actions Taken / How Issues Were Addressed')

# 25. Blank
doc.add_paragraph()

# 25. Table 2 - Actions
table2 = doc.add_table(rows=6, cols=4)
table2.style = 'Light Grid'

table2.rows[0].cells[0].text = 'S.No'
table2.rows[0].cells[1].text = 'Question / Issue'
table2.rows[0].cells[2].text = 'Action Taken'
table2.rows[0].cells[3].text = 'Status'

table2.rows[1].cells[0].text = '1'
table2.rows[1].cells[1].text = 'Sensor noise in feature extraction'
table2.rows[1].cells[2].text = 'Implemented statistical outlier rejection and adaptive filtering'
table2.rows[1].cells[3].text = 'Done'

table2.rows[2].cells[0].text = '2'
table2.rows[2].cells[1].text = 'Model overfitting on limited data'
table2.rows[2].cells[2].text = 'Implemented ensemble methods and cross-validation'
table2.rows[2].cells[3].text = 'Done'

table2.rows[3].cells[0].text = '3'
table2.rows[3].cells[1].text = 'Real-time latency requirements'
table2.rows[3].cells[2].text = 'Optimized feature extraction and inference paths'
table2.rows[3].cells[3].text = 'Done'

table2.rows[4].cells[0].text = '4'
table2.rows[4].cells[1].text = 'Sleep stage classification accuracy'
table2.rows[4].cells[2].text = 'Implemented 6 different models with rule-based fallback'
table2.rows[4].cells[3].text = 'Done'

table2.rows[5].cells[0].text = '5'
table2.rows[5].cells[1].text = 'Validation data scarcity'
table2.rows[5].cells[2].text = 'Created synthetic validation with physiological patterns'
table2.rows[5].cells[3].text = 'Done'

# 26. Challenges heading
p26 = doc.add_paragraph('7. Challenges Faced')

# 27-29. Blank
doc.add_paragraph()
doc.add_paragraph()
doc.add_paragraph()

# 30. Plan for Next Review heading
p30 = doc.add_paragraph('8. Plan for Next Review')

# 31-32. Blank
doc.add_paragraph()
doc.add_paragraph()

# 33. Expected Milestones heading
p33 = doc.add_paragraph('Expected Milestones:')

# 34-35. Blank
doc.add_paragraph()
doc.add_paragraph()

# 36. Remarks heading
p36 = doc.add_paragraph('9. Remarks by Guide')

# 37-38. Blank
doc.add_paragraph()
doc.add_paragraph()

# 39. Signatures heading
p39 = doc.add_paragraph('10. Signatures')

# 40. Student signature
p40 = doc.add_paragraph('Student(s): _______________________')

# 41. Guide signature
p41 = doc.add_paragraph('Guide: ____________________________')

# 42. Blank
doc.add_paragraph()

# Save document
output_path = r'SLEEP_DETECTION_PROJECT_REVIEW_STATUS_REPORT.docx'
doc.save(output_path)
print(f'Report created in exact template format: {output_path}')

from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QProgressBar,
							 QLabel, QApplication, QFrame)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPainter
import sys
import math


class TiltedLabel(QLabel):
	def __init__(self, text, parent=None):
		super().__init__(text, parent)
		self.setAlignment(Qt.AlignmentFlag.AlignCenter)

	def paintEvent(self, event):
		painter = QPainter(self)
		painter.setRenderHint(QPainter.RenderHint.Antialiasing)
		painter.translate(self.width() / 2, self.height() / 2)
		painter.rotate(45)
		painter.translate(-self.width() / 2, -self.height() / 2)
		painter.drawText(self.rect(), self.alignment(), self.text())


class MissionStatusWidget(QWidget):
	def __init__(self):
		super().__init__()
		self.init_ui()

	def init_ui(self):
		main_layout = QVBoxLayout(self)
		main_layout.setSpacing(20)
		self.progress_bar = QProgressBar()
		self.progress_bar.setRange(0, 100)
		self.progress_bar.setValue(0)
		self.progress_bar.setFixedHeight(25)

		self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #2c3e50;
                border-radius: 5px;
                text-align: center;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 3px;
            }
        """)

		main_layout.addWidget(self.progress_bar)
		labels_container = QFrame()
		labels_layout = QHBoxLayout(labels_container)
		labels_layout.setContentsMargins(0, 0, 0, 0)
		labels_layout.setSpacing(5)
		milestones = ["Calibration", "Start", "Engine", "Apogee", "Recovery", "Landing"]
		milestone_positions = [16, 33, 50, 66, 83, 100]
		labels_layout.addSpacing(5)

		for i, (milestone, position) in enumerate(zip(milestones, milestone_positions)):
			label = TiltedLabel(milestone)
			label.setFixedSize(100, 100)

			if position <= self.progress_bar.value():
				label.setStyleSheet("""
                    QLabel {
                        color: #3498db;
                        font-weight: bold;
                        background-color: transparent;
                        font-size: 20px;
                    }
                """)
			else:
				label.setStyleSheet("""
                    QLabel {
                        color: #7f8c8d;
                        background-color: transparent;
                        font-size: 20px;
                    }
                """)
			font = QFont()
			font.setPointSize(8)
			label.setFont(font)
			labels_layout.addWidget(label)

			if i < len(milestones) - 1:
				next_position = milestone_positions[i + 1]
				space_percentage = (next_position - position) / 100.0
				space = int(space_percentage * self.progress_bar.width() - 70)
				if space > 0:
					labels_layout.addSpacing(space)

		labels_layout.addSpacing(5)
		main_layout.addWidget(labels_container)

		self.setLayout(main_layout)
		self.setWindowTitle("Mission Status")
		self.setMinimumWidth(500)

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import QVBoxLayout, QWidget
from datetime import datetime


class TimeSeriesPlot(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground('k')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setLabel('left', 'Value')
        self.plot_widget.setLabel('bottom', 'Time')

        self.plot_widget.setMouseEnabled(x=True, y=True)
        self.plot_widget.setMenuEnabled(False)

        self.curve = self.plot_widget.plot(
            pen=pg.mkPen('y', width=2),
            name='Data Stream'
        )

        self.timestamps = np.array([], dtype=np.float64)
        self.values = np.array([], dtype=np.float64)

        self.min_time = None
        self.max_time = None
        self.min_value = float('inf')
        self.max_value = float('-inf')

        layout = QVBoxLayout()
        layout.addWidget(self.plot_widget)
        self.setLayout(layout)

        self.crosshair_v = pg.InfiniteLine(angle=90,
                                           movable=False)
        self.crosshair_h = pg.InfiniteLine(angle=0,
                                           movable=False)
        self.plot_widget.addItem(self.crosshair_v,
                                 ignoreBounds=True)
        self.plot_widget.addItem(self.crosshair_h,
                                 ignoreBounds=True)

        self.coord_label = pg.TextItem(anchor=(0, 1))
        self.coord_label.setPos(
            self.plot_widget.getAxis('bottom').range[0],
            self.plot_widget.getAxis('left').range[1])
        self.plot_widget.addItem(self.coord_label)

        self.plot_widget.scene().sigMouseMoved.connect(
            self.mouse_moved)

    def set_x_label(self, label):
        self.plot_widget.setLabel('bottom', label)

    def set_y_label(self, label):
        self.plot_widget.setLabel('left', label)

    def add_point(self, timestamp, value):

        if len(self.timestamps) >= 200:
            self.timestamps = self.timestamps[1:]
            self.values = self.values[1:]

        if isinstance(timestamp, datetime):
            ts = timestamp.timestamp()
        elif isinstance(timestamp, float):
            ts = timestamp
        else:
            ts = timestamp

        self.timestamps = np.append(self.timestamps, ts)
        self.values = np.append(self.values, value)

        if self.min_time is None or ts < self.min_time:
            self.min_time = ts
        if self.max_time is None or ts > self.max_time:
            self.max_time = ts
        if value < self.min_value:
            self.min_value = value
        if value > self.max_value:
            self.max_value = value

        self.update_plot()

    def set_data(self, timestamps, values):
        if isinstance(timestamps[0], datetime):
            self.timestamps = np.array(
                [t.timestamp() for t in timestamps])
        else:
            self.timestamps = np.array(timestamps)

        self.values = np.array(values)

        if len(self.timestamps) > 0:
            self.min_time = np.min(self.timestamps)
            self.max_time = np.max(self.timestamps)
            self.min_value = np.min(self.values)
            self.max_value = np.max(self.values)
        else:
            self.min_time = None
            self.max_time = None
            self.min_value = float('inf')
            self.max_value = float('-inf')

        self.update_plot()

    def update_plot(self):
        self.curve.setData(self.timestamps, self.values)

        if self.min_time is not None and self.max_time is not None:
            time_span = self.max_time - self.min_time
            padding = time_span * 0.05

            value_span = self.max_value - self.min_value
            value_padding = value_span * 0.1 if value_span > 0 else abs(
                self.min_value) * 0.1

            self.plot_widget.setXRange(
                self.min_time - padding,
                self.max_time + padding,
                padding=0
            )
            self.plot_widget.setYRange(
                self.min_value - value_padding,
                self.max_value + value_padding,
                padding=0
            )

        self.plot_widget.setAxisItems(
            {'bottom': pg.DateAxisItem()})

    def reset_view(self):
        self.update_plot()

    def mouse_moved(self, pos):
        if self.plot_widget.sceneBoundingRect().contains(
                pos):
            mouse_point = self.plot_widget.plotItem.vb.mapSceneToView(
                pos)
            x_val = mouse_point.x()
            y_val = mouse_point.y()

            self.crosshair_v.setPos(x_val)
            self.crosshair_h.setPos(y_val)

            dt = datetime.fromtimestamp(x_val)
            self.coord_label.setText(
                f"Time: {dt.strftime('%Y-%m-%d %H:%M:%S')}\nValue: {y_val:.4f}",
                color='w'
            )

    def clear_data(self):
        self.timestamps = []
        self.values = []
        self.update_plot()
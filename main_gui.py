#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import json
import asyncio
import threading
import time
import datetime
from collections import deque

from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                             QHBoxLayout, QGridLayout, QLabel, QPushButton, QDoubleSpinBox, 
                             QComboBox, QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
                             QGroupBox, QLineEdit, QSplitter, QStatusBar, QFrame)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QObject, QUrl
from PyQt5.QtGui import QFont, QIcon, QPixmap, QColor, QDesktopServices

import matplotlib
matplotlib.use('Qt5Agg')
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

# main.py dosyasından fonksiyonları import et
from main import fetch_currency_rates, calculate_trend, check_alarms, calculate_change

# Veri yapıları
currency_history = {
    'USD': deque(maxlen=60),
    'EUR': deque(maxlen=60),
    'GBP': deque(maxlen=60),
    'JPY': deque(maxlen=60),
    'CHF': deque(maxlen=60),
    'CAD': deque(maxlen=60),
    'AUD': deque(maxlen=60),
}

timestamp_history = deque(maxlen=60)

# Alarm seviyeleri
alarm_levels = {
    'USD': {'min': 0, 'max': float('inf')},
    'EUR': {'min': 0, 'max': float('inf')},
    'GBP': {'min': 0, 'max': float('inf')},
}

# Grafikler için renkler
chart_colors = {
    'USD': '#3498db',  # Mavi
    'EUR': '#e74c3c',  # Kırmızı
    'GBP': '#2ecc71',  # Yeşil
    'JPY': '#9b59b6',  # Mor
    'CHF': '#f39c12',  # Turuncu
    'CAD': '#1abc9c',  # Turkuaz
    'AUD': '#d35400',  # Turuncu-kırmızı
}


class CurrencySignals(QObject):
    """PyQt sinyalleri için yardımcı sınıf"""
    currency_updated = pyqtSignal(dict)
    alarm_triggered = pyqtSignal(str, str)


class MplCanvas(FigureCanvas):
    """Matplotlib grafikleri için özel canvas sınıfı"""
    def __init__(self):
        self.fig = Figure(figsize=(5, 4), dpi=100)
        self.axes = self.fig.add_subplot(111)
        super(MplCanvas, self).__init__(self.fig)
        self.fig.tight_layout()


class CurrencyWorker(threading.Thread):
    """Arka planda döviz kurlarını güncelleyen thread"""
    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.daemon = True
        self.running = True
        
    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        while self.running:
            try:
                # Döviz kurlarını al
                rates = loop.run_until_complete(fetch_currency_rates())
                
                # Zaman damgası ekle
                timestamp = datetime.datetime.now()
                rates['timestamp'] = timestamp.strftime("%H:%M:%S")
                rates['date'] = timestamp.strftime("%Y-%m-%d")
                timestamp_history.append(rates['timestamp'])
                
                # Geçmiş verileri güncelle
                for currency, rate in rates.items():
                    if currency in currency_history and currency not in ['timestamp', 'date']:
                        currency_history[currency].append(rate)
                
                # Hesaplamalar
                rates['USD_EUR'] = rates['USD'] / rates['EUR']
                rates['EUR_GBP'] = rates['EUR'] / rates['GBP']
                
                # Trend analizi
                trends = {currency: calculate_trend(currency) for currency in ['USD', 'EUR', 'GBP']}
                rates['trends'] = trends
                
                # Değişim yüzdeleri
                changes = {currency: calculate_change(currency) for currency in ['USD', 'EUR', 'GBP', 'JPY', 'CHF', 'CAD', 'AUD']}
                rates['changes'] = changes
                
                # Alarm kontrolü
                alarms = check_alarms(rates)
                if alarms:
                    rates['alarms'] = alarms
                    for currency, status in alarms.items():
                        message = f"{currency} kurları {'maksimum' if status == 'high' else 'minimum'} değerin {'üzerine çıktı' if status == 'high' else 'altına düştü'}!"
                        self.signals.alarm_triggered.emit(currency, message)
                
                # Sinyali gönder
                self.signals.currency_updated.emit(rates)
                
                # 5 saniye bekle
                time.sleep(5)
                
            except Exception as e:
                print(f"Hata: {e}")
                time.sleep(10)  # Hata durumunda 10 saniye bekle
    
    def stop(self):
        self.running = False


class DovizTakipApp(QMainWindow):
    """Ana uygulama penceresi"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Döviz Takip")
        self.setMinimumSize(900, 700)
        
        # PyQt sinyalleri
        self.signals = CurrencySignals()
        self.signals.currency_updated.connect(self.update_currency_data)
        self.signals.alarm_triggered.connect(self.show_alarm)
        
        # Ana widget ve layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        
        # Sekme widget'ını oluştur
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)
        
        # Sekmeleri oluştur
        self.create_main_tab()
        self.create_converter_tab()
        self.create_chart_tab()
        self.create_alarms_tab()
        self.create_history_tab()
        self.create_about_tab()
        
        # Durum çubuğu
        self.statusBar = QStatusBar()
        self.setStatusBar(self.statusBar)
        self.last_update_label = QLabel("Son Güncelleme: Bekleniyor...")
        self.statusBar.addWidget(self.last_update_label)
        
        # Veri yüklemesi başlat
        self.worker = CurrencyWorker(self.signals)
        self.worker.start()
        
        # İlk kez durum çubuğu güncelleme
        self.update_status_bar()
        
        # Düzenli durum çubuğu güncellemesi için zamanlayıcı
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start(10000)  # 10 saniyede bir güncelle
    
    def create_main_tab(self):
        """Ana sekmeyi oluşturur - temel döviz bilgileri"""
        main_tab = QWidget()
        layout = QVBoxLayout(main_tab)
        
        # Günün tarihi
        date_layout = QHBoxLayout()
        self.date_label = QLabel("14 Nisan 2025")
        self.date_label.setAlignment(Qt.AlignRight)
        self.date_label.setStyleSheet("font-size: 14px; color: #555;")
        date_layout.addStretch()
        date_layout.addWidget(self.date_label)
        layout.addLayout(date_layout)
        
        # Ana para birimleri (USD, EUR, GBP)
        main_currency_group = QGroupBox("Ana Para Birimleri")
        main_currency_layout = QGridLayout()
        
        # Başlık satırı
        main_currency_layout.addWidget(QLabel("Para Birimi"), 0, 0)
        main_currency_layout.addWidget(QLabel("Değer (TRY)"), 0, 1)
        main_currency_layout.addWidget(QLabel("Trend"), 0, 2)
        main_currency_layout.addWidget(QLabel("Değişim"), 0, 3)
        
        # USD
        main_currency_layout.addWidget(QLabel("USD (Dolar)"), 1, 0)
        self.usd_label = QLabel("Yükleniyor...")
        self.usd_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #3498db;")
        main_currency_layout.addWidget(self.usd_label, 1, 1)
        self.usd_trend = QLabel("")
        main_currency_layout.addWidget(self.usd_trend, 1, 2)
        self.usd_change = QLabel("")
        main_currency_layout.addWidget(self.usd_change, 1, 3)
        
        # EUR
        main_currency_layout.addWidget(QLabel("EUR (Euro)"), 2, 0)
        self.eur_label = QLabel("Yükleniyor...")
        self.eur_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #3498db;")
        main_currency_layout.addWidget(self.eur_label, 2, 1)
        self.eur_trend = QLabel("")
        main_currency_layout.addWidget(self.eur_trend, 2, 2)
        self.eur_change = QLabel("")
        main_currency_layout.addWidget(self.eur_change, 2, 3)
        
        # GBP
        main_currency_layout.addWidget(QLabel("GBP (Sterlin)"), 3, 0)
        self.gbp_label = QLabel("Yükleniyor...")
        self.gbp_label.setStyleSheet("font-size: 15px; font-weight: bold; color: #3498db;")
        main_currency_layout.addWidget(self.gbp_label, 3, 1)
        self.gbp_trend = QLabel("")
        main_currency_layout.addWidget(self.gbp_trend, 3, 2)
        self.gbp_change = QLabel("")
        main_currency_layout.addWidget(self.gbp_change, 3, 3)
        
        main_currency_group.setLayout(main_currency_layout)
        layout.addWidget(main_currency_group)
        
        # Diğer para birimleri
        other_currency_group = QGroupBox("Diğer Para Birimleri")
        other_currency_layout = QGridLayout()
        
        # Başlık satırı
        other_currency_layout.addWidget(QLabel("Para Birimi"), 0, 0)
        other_currency_layout.addWidget(QLabel("Değer (TRY)"), 0, 1)
        other_currency_layout.addWidget(QLabel("Para Birimi"), 0, 2)
        other_currency_layout.addWidget(QLabel("Değer (TRY)"), 0, 3)
        
        # İlk sütun
        other_currency_layout.addWidget(QLabel("JPY (Japon Yeni)"), 1, 0)
        self.jpy_label = QLabel("Yükleniyor...")
        other_currency_layout.addWidget(self.jpy_label, 1, 1)
        
        other_currency_layout.addWidget(QLabel("CHF (İsviçre Frangı)"), 2, 0)
        self.chf_label = QLabel("Yükleniyor...")
        other_currency_layout.addWidget(self.chf_label, 2, 1)
        
        # İkinci sütun
        other_currency_layout.addWidget(QLabel("CAD (Kanada Doları)"), 1, 2)
        self.cad_label = QLabel("Yükleniyor...")
        other_currency_layout.addWidget(self.cad_label, 1, 3)
        
        other_currency_layout.addWidget(QLabel("AUD (Avustralya Doları)"), 2, 2)
        self.aud_label = QLabel("Yükleniyor...")
        other_currency_layout.addWidget(self.aud_label, 2, 3)
        
        other_currency_group.setLayout(other_currency_layout)
        layout.addWidget(other_currency_group)
        
        # Çapraz kurlar
        cross_currency_group = QGroupBox("Çapraz Kurlar")
        cross_currency_layout = QGridLayout()
        
        cross_currency_layout.addWidget(QLabel("USD/EUR:"), 0, 0)
        self.usd_eur_label = QLabel("Yükleniyor...")
        cross_currency_layout.addWidget(self.usd_eur_label, 0, 1)
        
        cross_currency_layout.addWidget(QLabel("EUR/GBP:"), 1, 0)
        self.eur_gbp_label = QLabel("Yükleniyor...")
        cross_currency_layout.addWidget(self.eur_gbp_label, 1, 1)
        
        cross_currency_group.setLayout(cross_currency_layout)
        layout.addWidget(cross_currency_group)
        
        layout.addStretch()
        self.tabs.addTab(main_tab, "Ana Sayfa")

    def create_converter_tab(self):
        """Döviz hesaplama sekmesini oluşturur"""
        converter_tab = QWidget()
        layout = QVBoxLayout(converter_tab)
        
        converter_group = QGroupBox("Döviz Hesaplayıcı")
        converter_layout = QGridLayout()
        
        # Miktar
        converter_layout.addWidget(QLabel("Miktar:"), 0, 0)
        self.amount_input = QDoubleSpinBox()
        self.amount_input.setRange(0.01, 1000000.00)
        self.amount_input.setValue(1.00)
        self.amount_input.setSingleStep(1.00)
        self.amount_input.setDecimals(2)
        converter_layout.addWidget(self.amount_input, 0, 1)
        
        # Kaynak para birimi
        converter_layout.addWidget(QLabel("Kaynak Para Birimi:"), 1, 0)
        self.source_currency = QComboBox()
        self.source_currency.addItems(["USD (Dolar)", "EUR (Euro)", "GBP (Sterlin)", "TRY (Türk Lirası)", 
                                      "JPY (Japon Yeni)", "CHF (İsviçre Frangı)", "CAD (Kanada Doları)", "AUD (Avustralya Doları)"])
        converter_layout.addWidget(self.source_currency, 1, 1)
        
        # Hedef para birimi
        converter_layout.addWidget(QLabel("Hedef Para Birimi:"), 2, 0)
        self.target_currency = QComboBox()
        self.target_currency.addItems(["TRY (Türk Lirası)", "USD (Dolar)", "EUR (Euro)", "GBP (Sterlin)", 
                                      "JPY (Japon Yeni)", "CHF (İsviçre Frangı)", "CAD (Kanada Doları)", "AUD (Avustralya Doları)"])
        converter_layout.addWidget(self.target_currency, 2, 1)
        
        # Hesaplama butonu
        convert_button = QPushButton("Hesapla")
        convert_button.clicked.connect(self.convert_currency)
        converter_layout.addWidget(convert_button, 3, 0, 1, 2)
        
        # Sonuç
        converter_layout.addWidget(QLabel("Sonuç:"), 4, 0)
        self.result_label = QLabel("0.00")
        self.result_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #3498db;")
        converter_layout.addWidget(self.result_label, 4, 1)
        
        converter_group.setLayout(converter_layout)
        layout.addWidget(converter_group)
        layout.addStretch()
        
        self.tabs.addTab(converter_tab, "Döviz Hesaplama")

    def create_chart_tab(self):
        """Grafik sekmesini oluşturur"""
        chart_tab = QWidget()
        layout = QVBoxLayout(chart_tab)
        
        # Grafik seçimi
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Para Birimi:"))
        self.chart_currency = QComboBox()
        self.chart_currency.addItems(["USD (Dolar)", "EUR (Euro)", "GBP (Sterlin)", 
                                     "JPY (Japon Yeni)", "CHF (İsviçre Frangı)", 
                                     "CAD (Kanada Doları)", "AUD (Avustralya Doları)"])
        self.chart_currency.currentIndexChanged.connect(self.update_chart)
        selection_layout.addWidget(self.chart_currency)
        layout.addLayout(selection_layout)
        
        # Grafik canvas
        self.chart_canvas = MplCanvas()
        layout.addWidget(self.chart_canvas)
        
        self.tabs.addTab(chart_tab, "Grafikler")

    def create_alarms_tab(self):
        """Alarm ayarları sekmesini oluşturur"""
        alarms_tab = QWidget()
        layout = QVBoxLayout(alarms_tab)
        
        # USD Alarmları
        usd_group = QGroupBox("USD Alarmları")
        usd_layout = QGridLayout()
        
        usd_layout.addWidget(QLabel("Minimum (TRY):"), 0, 0)
        self.usd_min_alarm = QDoubleSpinBox()
        self.usd_min_alarm.setRange(0.00, 100.00)
        self.usd_min_alarm.setSingleStep(0.10)
        self.usd_min_alarm.setDecimals(2)
        usd_layout.addWidget(self.usd_min_alarm, 0, 1)
        
        usd_min_button = QPushButton("Ayarla")
        usd_min_button.clicked.connect(lambda: self.set_alarm("USD", "min"))
        usd_layout.addWidget(usd_min_button, 0, 2)
        
        usd_layout.addWidget(QLabel("Maksimum (TRY):"), 1, 0)
        self.usd_max_alarm = QDoubleSpinBox()
        self.usd_max_alarm.setRange(0.00, 100.00)
        self.usd_max_alarm.setSingleStep(0.10)
        self.usd_max_alarm.setDecimals(2)
        usd_layout.addWidget(self.usd_max_alarm, 1, 1)
        
        usd_max_button = QPushButton("Ayarla")
        usd_max_button.clicked.connect(lambda: self.set_alarm("USD", "max"))
        usd_layout.addWidget(usd_max_button, 1, 2)
        
        usd_group.setLayout(usd_layout)
        layout.addWidget(usd_group)
        
        # EUR Alarmları
        eur_group = QGroupBox("EUR Alarmları")
        eur_layout = QGridLayout()
        
        eur_layout.addWidget(QLabel("Minimum (TRY):"), 0, 0)
        self.eur_min_alarm = QDoubleSpinBox()
        self.eur_min_alarm.setRange(0.00, 100.00)
        self.eur_min_alarm.setSingleStep(0.10)
        self.eur_min_alarm.setDecimals(2)
        eur_layout.addWidget(self.eur_min_alarm, 0, 1)
        
        eur_min_button = QPushButton("Ayarla")
        eur_min_button.clicked.connect(lambda: self.set_alarm("EUR", "min"))
        eur_layout.addWidget(eur_min_button, 0, 2)
        
        eur_layout.addWidget(QLabel("Maksimum (TRY):"), 1, 0)
        self.eur_max_alarm = QDoubleSpinBox()
        self.eur_max_alarm.setRange(0.00, 100.00)
        self.eur_max_alarm.setSingleStep(0.10)
        self.eur_max_alarm.setDecimals(2)
        eur_layout.addWidget(self.eur_max_alarm, 1, 1)
        
        eur_max_button = QPushButton("Ayarla")
        eur_max_button.clicked.connect(lambda: self.set_alarm("EUR", "max"))
        eur_layout.addWidget(eur_max_button, 1, 2)
        
        eur_group.setLayout(eur_layout)
        layout.addWidget(eur_group)
        
        # GBP Alarmları
        gbp_group = QGroupBox("GBP Alarmları")
        gbp_layout = QGridLayout()
        
        gbp_layout.addWidget(QLabel("Minimum (TRY):"), 0, 0)
        self.gbp_min_alarm = QDoubleSpinBox()
        self.gbp_min_alarm.setRange(0.00, 100.00)
        self.gbp_min_alarm.setSingleStep(0.10)
        self.gbp_min_alarm.setDecimals(2)
        gbp_layout.addWidget(self.gbp_min_alarm, 0, 1)
        
        gbp_min_button = QPushButton("Ayarla")
        gbp_min_button.clicked.connect(lambda: self.set_alarm("GBP", "min"))
        gbp_layout.addWidget(gbp_min_button, 0, 2)
        
        gbp_layout.addWidget(QLabel("Maksimum (TRY):"), 1, 0)
        self.gbp_max_alarm = QDoubleSpinBox()
        self.gbp_max_alarm.setRange(0.00, 100.00)
        self.gbp_max_alarm.setSingleStep(0.10)
        self.gbp_max_alarm.setDecimals(2)
        gbp_layout.addWidget(self.gbp_max_alarm, 1, 1)
        
        gbp_max_button = QPushButton("Ayarla")
        gbp_max_button.clicked.connect(lambda: self.set_alarm("GBP", "max"))
        gbp_layout.addWidget(gbp_max_button, 1, 2)
        
        gbp_group.setLayout(gbp_layout)
        layout.addWidget(gbp_group)
        
        layout.addStretch()
        
        self.tabs.addTab(alarms_tab, "Alarmlar")

    def create_history_tab(self):
        """Geçmiş veriler sekmesini oluşturur"""
        history_tab = QWidget()
        layout = QVBoxLayout(history_tab)
        
        # Tablo
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(5)
        self.history_table.setHorizontalHeaderLabels(["Zaman", "USD/TRY", "EUR/TRY", "GBP/TRY", "Değişim (USD)"])
        self.history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.history_table)
        
        self.tabs.addTab(history_tab, "Geçmiş")

    def create_about_tab(self):
        """Hakkında sekmesini oluşturur"""
        about_tab = QWidget()
        layout = QVBoxLayout(about_tab)
        
        # Logo veya görsel
        try:
            logo_label = QLabel()
            pixmap = QPixmap("images/doviz.jpeg")
            if not pixmap.isNull():
                pixmap = pixmap.scaled(300, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(pixmap)
                logo_label.setAlignment(Qt.AlignCenter)
                layout.addWidget(logo_label)
        except:
            pass
        
        # Başlık
        title = QLabel("Döviz Takip")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 24px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)
        
        # Açıklama
        description = QLabel("Gerçek zamanlı döviz kuru takip ve analiz uygulaması.")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Geliştirici bilgileri
        developer = QLabel("© 2025 Hamza ORTATEPE")
        developer.setAlignment(Qt.AlignCenter)
        layout.addWidget(developer)
        
        # GitHub linki
        github_button = QPushButton("GitHub")
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl("https://github.com/hamer1818")))
        layout.addWidget(github_button)
        
        layout.addStretch()
        
        self.tabs.addTab(about_tab, "Hakkında")

    def update_currency_data(self, data):
        """Döviz verilerini günceller"""
        # Ana para birimleri
        self.usd_label.setText(f"{data['USD']:.4f} ₺")
        self.eur_label.setText(f"{data['EUR']:.4f} ₺")
        self.gbp_label.setText(f"{data['GBP']:.4f} ₺")
        
        # Ekstra para birimleri
        self.jpy_label.setText(f"{data['JPY']:.4f} ₺")
        self.chf_label.setText(f"{data['CHF']:.4f} ₺")
        self.cad_label.setText(f"{data['CAD']:.4f} ₺")
        self.aud_label.setText(f"{data['AUD']:.4f} ₺")
        
        # Çapraz kurlar
        self.usd_eur_label.setText(f"{data['USD_EUR']:.4f}")
        self.eur_gbp_label.setText(f"{data['EUR_GBP']:.4f}")
        
        # Trend göstergeleri
        self.update_trend_indicators(data)
        
        # Değişim göstergeleri
        self.update_change_indicators(data)
        
        # Geçmiş veriler tablosu
        self.update_history_table()
        
        # Grafikler
        self.update_chart()
        
        # Tarih ve durum çubuğu
        self.date_label.setText(data['date'])
        self.last_update_label.setText(f"Son Güncelleme: {data['timestamp']}")
    
    def update_trend_indicators(self, data):
        """Trend göstergelerini günceller"""
        if 'trends' in data:
            trends = data['trends']
            
            # USD Trend
            if trends['USD'] == 'yükseliyor':
                self.usd_trend.setText("▲")
                self.usd_trend.setStyleSheet("color: green; font-weight: bold;")
            elif trends['USD'] == 'düşüyor':
                self.usd_trend.setText("▼")
                self.usd_trend.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.usd_trend.setText("―")
                self.usd_trend.setStyleSheet("color: gray; font-weight: bold;")
            
            # EUR Trend
            if trends['EUR'] == 'yükseliyor':
                self.eur_trend.setText("▲")
                self.eur_trend.setStyleSheet("color: green; font-weight: bold;")
            elif trends['EUR'] == 'düşüyor':
                self.eur_trend.setText("▼")
                self.eur_trend.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.eur_trend.setText("―")
                self.eur_trend.setStyleSheet("color: gray; font-weight: bold;")
            
            # GBP Trend
            if trends['GBP'] == 'yükseliyor':
                self.gbp_trend.setText("▲")
                self.gbp_trend.setStyleSheet("color: green; font-weight: bold;")
            elif trends['GBP'] == 'düşüyor':
                self.gbp_trend.setText("▼")
                self.gbp_trend.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.gbp_trend.setText("―")
                self.gbp_trend.setStyleSheet("color: gray; font-weight: bold;")
    
    def update_change_indicators(self, data):
        """Değişim göstergelerini günceller"""
        if 'changes' in data:
            changes = data['changes']
            
            # USD Change
            if changes['USD']['percent'] > 0:
                self.usd_change.setText(f"+{changes['USD']['percent']:.2f}%")
                self.usd_change.setStyleSheet("color: green;")
            elif changes['USD']['percent'] < 0:
                self.usd_change.setText(f"{changes['USD']['percent']:.2f}%")
                self.usd_change.setStyleSheet("color: red;")
            else:
                self.usd_change.setText("0.00%")
                self.usd_change.setStyleSheet("color: gray;")
            
            # EUR Change
            if changes['EUR']['percent'] > 0:
                self.eur_change.setText(f"+{changes['EUR']['percent']:.2f}%")
                self.eur_change.setStyleSheet("color: green;")
            elif changes['EUR']['percent'] < 0:
                self.eur_change.setText(f"{changes['EUR']['percent']:.2f}%")
                self.eur_change.setStyleSheet("color: red;")
            else:
                self.eur_change.setText("0.00%")
                self.eur_change.setStyleSheet("color: gray;")
            
            # GBP Change
            if changes['GBP']['percent'] > 0:
                self.gbp_change.setText(f"+{changes['GBP']['percent']:.2f}%")
                self.gbp_change.setStyleSheet("color: green;")
            elif changes['GBP']['percent'] < 0:
                self.gbp_change.setText(f"{changes['GBP']['percent']:.2f}%")
                self.gbp_change.setStyleSheet("color: red;")
            else:
                self.gbp_change.setText("0.00%")
                self.gbp_change.setStyleSheet("color: gray;")
    
    def update_chart(self):
        """Seçilen para birimi için grafiği günceller"""
        selected_item = self.chart_currency.currentText().split(" ")[0]
        
        if len(currency_history[selected_item]) < 2:
            return
        
        # Grafik verilerini ayarla
        x_data = list(timestamp_history)
        y_data = list(currency_history[selected_item])
        
        # Grafik temizle
        self.chart_canvas.axes.clear()
        
        # Grafik çiz
        self.chart_canvas.axes.plot(x_data, y_data, color=chart_colors.get(selected_item, '#3498db'), marker='o', markersize=4)
        self.chart_canvas.axes.set_title(f"{selected_item}/TRY Döviz Kuru")
        self.chart_canvas.axes.set_ylabel("TRY Değeri")
        self.chart_canvas.axes.grid(True, linestyle='--', alpha=0.7)
        
        # X eksenindeki tarih etiketlerinin dönüklüğünü ayarla
        self.chart_canvas.axes.tick_params(axis='x', rotation=45)
        
        # Görünen etiket sayısını azalt (her 5. etiketi göster)
        if len(x_data) > 10:
            n_labels = len(x_data)
            step = max(1, n_labels // 10)  # En fazla 10 etiket göster
            self.chart_canvas.axes.set_xticks(x_data[::step])
            self.chart_canvas.axes.set_xticklabels(x_data[::step])
        
        # Grafiği güncelle
        self.chart_canvas.fig.tight_layout()
        self.chart_canvas.draw()
    
    def update_history_table(self):
        """Geçmiş veriler tablosunu günceller"""
        # Tablodaki satır sayısını ayarla
        n_rows = len(timestamp_history)
        self.history_table.setRowCount(n_rows)
        
        # Tabloya verileri ekle - ters sırayla en son veri en üstte olsun
        for i in range(n_rows):
            idx = n_rows - i - 1  # Ters sıra
            
            # Zaman
            time_item = QTableWidgetItem(timestamp_history[idx] if idx < len(timestamp_history) else "")
            self.history_table.setItem(i, 0, time_item)
            
            # USD/TRY
            if idx < len(currency_history['USD']):
                usd_item = QTableWidgetItem(f"{list(currency_history['USD'])[idx]:.4f}")
                self.history_table.setItem(i, 1, usd_item)
            
            # EUR/TRY
            if idx < len(currency_history['EUR']):
                eur_item = QTableWidgetItem(f"{list(currency_history['EUR'])[idx]:.4f}")
                self.history_table.setItem(i, 2, eur_item)
            
            # GBP/TRY
            if idx < len(currency_history['GBP']):
                gbp_item = QTableWidgetItem(f"{list(currency_history['GBP'])[idx]:.4f}")
                self.history_table.setItem(i, 3, gbp_item)
            
            # Değişim (USD)
            if idx < len(currency_history['USD']) - 1:
                current = list(currency_history['USD'])[idx]
                previous = list(currency_history['USD'])[idx+1]
                change_percent = ((current - previous) / previous * 100) if previous != 0 else 0
                
                change_text = f"{change_percent:+.2f}%" if change_percent != 0 else "0.00%"
                change_item = QTableWidgetItem(change_text)
                
                # Renklendirme
                if change_percent > 0:
                    change_item.setForeground(QColor(0, 128, 0))  # Yeşil
                elif change_percent < 0:
                    change_item.setForeground(QColor(255, 0, 0))  # Kırmızı
                
                self.history_table.setItem(i, 4, change_item)
    
    def convert_currency(self):
        """Para birimi dönüşümü yapar"""
        amount = self.amount_input.value()
        source = self.source_currency.currentText().split(" ")[0]
        target = self.target_currency.currentText().split(" ")[0]
        
        currency_rates = {}
        
        # En son kurları al
        for currency in currency_history:
            if currency_history[currency]:
                currency_rates[currency] = currency_history[currency][-1]
        
        # TRY ekleniyor
        currency_rates['TRY'] = 1.0
        
        if source in currency_rates and target in currency_rates:
            if source == 'TRY':
                # TRY'den başka para birimine
                result = amount / currency_rates[target]
            elif target == 'TRY':
                # Başka para biriminden TRY'ye
                result = amount * currency_rates[source]
            else:
                # Çapraz kur hesaplama
                source_in_try = amount * currency_rates[source]  # Önce TRY'ye çevir
                result = source_in_try / currency_rates[target]  # TRY'den hedef para birimine
            
            # Para birimi sembolünü al
            symbol = self.get_currency_symbol(target)
            
            # Sonucu göster
            self.result_label.setText(f"{result:.4f} {symbol}")
        else:
            self.result_label.setText("Hesaplanamıyor")
    
    def get_currency_symbol(self, currency):
        """Para birimi sembolünü döndürür"""
        symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'TRY': '₺',
            'JPY': '¥',
            'CHF': 'CHF',
            'CAD': 'C$',
            'AUD': 'A$'
        }
        return symbols.get(currency, currency)
    
    def set_alarm(self, currency, alarm_type):
        """Alarm seviyelerini ayarlar"""
        if currency == "USD":
            value = self.usd_min_alarm.value() if alarm_type == "min" else self.usd_max_alarm.value()
        elif currency == "EUR":
            value = self.eur_min_alarm.value() if alarm_type == "min" else self.eur_max_alarm.value()
        elif currency == "GBP":
            value = self.gbp_min_alarm.value() if alarm_type == "min" else self.gbp_max_alarm.value()
        else:
            return
        
        # Alarmı ayarla
        alarm_levels[currency][alarm_type] = value
        
        # Kullanıcıyı bilgilendir
        QMessageBox.information(self, "Alarm Ayarlandı", 
                              f"{currency} için {alarm_type}imum alarm değeri {value:.2f} TRY olarak ayarlandı.")
    
    def show_alarm(self, currency, message):
        """Alarm bildirimi gösterir"""
        QMessageBox.warning(self, f"{currency} Alarm", message)
    
    def update_status_bar(self):
        """Durum çubuğunu günceller"""
        now = datetime.datetime.now()
        self.statusBar.showMessage(f"Aktif | {now.strftime('%H:%M:%S')}", 2000)
    
    def closeEvent(self, event):
        """Uygulama kapanırken çalışır"""
        # Thread'i durdur
        if hasattr(self, 'worker'):
            self.worker.stop()
        
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # Modern görünüm
    
    # Uygulama fontu
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    # Ana pencereyi göster
    window = DovizTakipApp()
    window.show()
    
    sys.exit(app.exec_())
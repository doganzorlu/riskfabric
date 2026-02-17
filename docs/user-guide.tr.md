# Riskfabric Kullanici Kilavuzu (TR)

Bu kilavuz, kurumsal risk yonetimini sifirdan ogrenmek isteyen calisanlar icin hazirlanmistir. Menu hiyerarsisini takip eder, her kavrami ve ekrani ayrintili aciklar.

## Temeller

### Risk Nedir?

Risk, hedefleri etkileyebilecek olaylarin olasiligidir.
Tam bir risk ifadesi neden, olay ve etkiyi kapsar.
Ornek: Erisim gozetiminin eksikligi (neden) nedeniyle yetkili hesaplarin kotuye kullanimi (olay) olabilir, bu da hizmet kesintisi veya veri kaybi (etki) yaratabilir.
- Risk belirsizlik icerir. Kesinse bu bir olay veya sorundur.
- Risk her zaman bir varlik ve hedef ile iliskilidir.
- Risk bir kisi veya takimin sorumlulugundadir.
- Risk ifadeleri net ve uygulanabilir olmali.

### Risk Analizi

Risk analizi, olasilik ve etkinin degerlendirilmesiyle risk seviyesinin bulunmasidir.
Niteliksel, sayisal veya hibrit olabilir.
- Olasilik: olay olma ihtimali.
- Etki: olursa ne kadar zarar verir.
- Mevcut kontroller: olasiligi veya etkiyi dusurur.
- Azaltma etkinligi: planlanan aksiyonun etkisi.
- Varsayimlar belgelendirilmelidir.

### Risk Degerlendirmesi Yasam Dongusu

1. Riski tanimla.
2. Olasilik ve etkiyi analiz et.
3. Kabul edilebilirligi degerlendir.
4. Azaltma planla.
5. Izle ve raporla.
6. Periyodik gozden gecir.

### Zafiyet Yonetimi

Zafiyet, istismar edilebilir zayifliktir.
Zafiyet analizi, etki ve olasiligi degerlendirir ve risklerle baglar.
- Zafiyetler varliklara baglidir.
- Zafiyetler risklerle iliskilendirilebilir.
- Zafiyet, olay gerceklesmeden once vardir.
- Onceliklendirme varlik kritikliligine gore yapilmalidir.

### Yonetisim ve Uyumluluk

Yonetisim karar haklarini ve hesap verebilirligi tanimlar.
Uyumluluk standart ve regulasyonlara uygunlugu kanitlar.
- Yonetisim programlari politika ve denetim yapisini kurar.
- Uyumluluk cerceveleri gereksinimleri tanimlar.
- Kontroller ve testler kanit saglar.


## Risk Yonetimi Kavramlari

### Risk Istahi ve Tolerans

Risk istahi, kabul edilebilir risk seviyesini tanimlar.
Risk toleransi, hedef etrafindaki kabul edilebilir sapmadir.
- Istah ust yonetim tarafindan belirlenir.
- Skor esikleri istaha gore ayarlanir.
- Tolerans, azaltma kararlarinda kullanilir.

### Risk Kategorileri

- Stratejik
- Operasyonel
- Finansal
- Uyumluluk
- Teknoloji
- Ucuncu Taraf

### Icsel ve Artik Risk

Icsel risk kontroller olmadan onceki seviyedir.
Artik risk kontrollerden sonra kalan seviyedir.
- Mumkunse her ikisini de kaydedin.
- Kararlar artik risk uzerinden verilir.


## Menu Genel Bakis

### Dashboard

Ana panel, erisim kapsamınıza gore metrik ve trendleri gosterir.
Operasyonel farkindalik icin kullanilir.

### Varliklar

- Varlik Siniflari
- Varliklar
- Varlik Bagimliliklari
- Lokasyon Agaci

### Riskler

- Risk Listesi
- Risk Detay (operasyon merkezi)
- Risk Azaltma
- Risk Gozden Gecirme
- Sorunlar ve Istisnalar

### Degerlendirmeler

- Degerlendirme Listesi
- Degerlendirme Detay

### Zafiyetler

- Zafiyet Listesi
- Zafiyet Detay

### Yonetisim

- Yonetisim Programlari
- Politikalar ve Standartlar

### Uyumluluk

- Uyumluluk Cerceveleri
- Gereksinimler
- Kontrol Test Planlari
- Kontrol Test Calismalari

### Raporlar

- Risk Ozeti
- Zafiyet Ozeti
- Uyumluluk Kapsami
- Kontrol Etkinligi
- CSV Export

### Sistem Parametreleri

- Risk Skor Yontemleri
- Kategoriler
- Etiketler
- Durum Kataloglari


## Veri Modeli

### Varlik

- Ad ve Kod: tanimlayicilar.
- Varlik Sinifi: ortak ozellikler.
- Lokasyon Metasi: isletme birimi, maliyet merkezi, bolum.
- Bagimliliklar: ust/alt iliskiler.
- Erisim: goren takmlar veya kullanicilar.

### Risk

- Baslik ve aciklama.
- Varlik.
- Olasilik ve etki.
- Skor (yonteme gore hesaplanir).
- Durum (taslak, aktif, azaltildi, kapandi).
- Sahip (sorumlu kisi/takim).

### Risk Skor Yontemi

- Yontem tipi: niteliksel veya sayisal.
- Agirliklar: olasilik, etki, azaltma.
- Varsayilan yontem.

### Azaltma

- Tip: kacin, azalt, aktar, kabul et.
- Sorumlu ve hedef tarih.
- Beklenen etkinlik ve durum.

### Gozden Gecirme

- Tarih, gozden geciren, sonuc.
- Sonraki gozden gecirme tarihi.

### Zafiyet

- Siddet, durum, ilgili riskler.

### Degerlendirme

- Kapsam, yontem, sahip, bulgular.

### Yonetisim Programi

- Program adi, sahip, durum, politikalar.

### Uyumluluk Cercevesi ve Gereksinim

- Cerceve adi.
- Gereksinim kodu ve aciklama.
- Haritalanan kontroller ve kanitlar.

### Kontrol Test Plani ve Calismasi

- Plan testin nasil yapilacagini belirler.
- Calisma gercek test sonucunu kaydeder.


## Alan Bazli Rehberler

### Risk Alanlari

Bu bolum Risk ekrani icin alan bazli rehberdir.

- Baslik: Riskin kisa ozeti.
  Ipucu: Fiil + nesne kullanin.
- Aciklama: Neden-olay-etki yapisinda ifade.
  Ipucu: Risk cumlesi sablonunu kullanin.
- Varlik: Riskin bagli oldugu varlik.
  Ipucu: En spesifik varligi secin.
- Olasilik: Olayin olma ihtimali.
  Ipucu: Gecmis veriye dayandir.
- Etki: Olursa zarar seviyesi.
  Ipucu: Finansal ve uyumluluk etkisi degerlendirin.
- Skor: Yonteme gore hesaplanir.
  Ipucu: Yontem dogru secili mi kontrol edin.
- Durum: Yasam dongusu durumu.
  Ipucu: Analiz bitmediyse Taslakta birakin.
- Sahip: Sorumlu kisi/takim.
  Ipucu: Aksiyon alabilecek kisi secin.
- Azaltma Etkinligi: Skoru dusurecek etki.
  Ipucu: Gercekci varsayim yapin.

### Zafiyet Alanlari

Bu bolum Zafiyet ekrani icin alan bazli rehberdir.

- Baslik: Zayifligin kisa ozeti.
  Ipucu: Bilesen adini ekleyin.
- Aciklama: Detay ve kanit.
  Ipucu: Scanner bulgusunu ekleyin.
- Varlik: Etkilenen varlik.
  Ipucu: Dogru varligi esleyin.
- Siddet: Istismarin etkisi.
  Ipucu: Standart skora uyun.
- Durum: Acik, Inceleme, Kapali.
  Ipucu: Dogrulamadan kapatmayin.
- Ilgili Riskler: Bagli riskler.
  Ipucu: Yoksa risk olusturun.


## Surec Bolumleri

### Surec Bolumu 1: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 2: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 3: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 4: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 5: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 6: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 7: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 8: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 9: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.

### Surec Bolumu 10: Operasyonel Risk Akisi

Amac: rol ve onaylariyla uc uca sureci aciklamak.
Adimlar:
- Yeni varliklar icin risk tanimla.
- Olasilik ve etkiyi analiz et.
- Skor yontemini uygula.
- Azaltma planini onaya sun.
- KRileri izle ve takvimli gozden gecir.
Kalite kontroller:
- Sahiplik dogru mu.
- Kontroller eslenmis mi.
- Artik risk kaydi var mi.



## Ekler

### Terimler

- Varlik: korunmasi gereken her sey.
- Risk: hedefleri etkileyebilecek olumsuz olay ihtimali.
- Azaltma: riski dusurmek icin aksiyon.
- Kontrol: riski azaltan mekanizma.
- Uyumluluk: standartlara uygunluk.

### Ornek Sablonlar

Risk kaydi ornegi: Varlik, Risk, Olasilik, Etki, Skor, Durum, Sahip, Azaltma.
Kontrol testi ornegi: Kontrol, Test Tarihi, Kanit, Sonuc.



## Vaka Calismalari

### Vaka Calismasi 1: ERP Erisim Gozden Gecirme Aksagi

Baglam: ERP icin periyodik erisim gozden gecirmeleri ertelendi ve yetkili hesaplar birikti.

Adimlar:
- ERP varligini kritik olarak isaretle ve bagimliliklari yaz.
- Neden-olay-etki yapisinda risk olustur.
- Gecikme kanitina gore olasiligi skorlendir.
- Azaltma: otomatik erisim gozden gecirme ve onay.
- Denetim kanitlariyla uc aylik gozden gecirme ayarla.

Sonuc: Artik risk azaldi; denetim kanitlariyla uyumluluk saglandi.

### Vaka Calismasi 2: Yamalanmamis OT Sistemleri

Baglam: Uretim PLC sistemleri durus nedeniyle kritik yamalari almadı.

Adimlar:
- OT varliklarini lokasyon metasi ile kaydet.
- Eksik yamalar icin zafiyet kaydi olustur.
- Zafiyetleri operasyonel risklere bagla.
- Bakim pencereleri planini azaltma olarak ekle.
- KRI olarak yama uyumlulugunu izle.

Sonuc: Yama uyumlulugu %90’a cikti ve risk skoru dustu.

### Vaka Calismasi 3: Ucuncu Taraf Lojistik Kesintisi

Baglam: Lojistik saglayicisi kesintisi teslimat gecikmelerine neden oldu.

Adimlar:
- Ucuncu taraf varligini ve bagimliliklarini tanimla.
- Gelir etkisine gore risk skorla.
- Azaltma: ikinci saglayici sozlesmesi.
- Yonetisim onaylarini kaydet.

Sonuc: Tedarik cesitliligi etkiyi azaltti.

### Vaka Calismasi 4: Veri Merkezi Enerji Dengesizligi

Baglam: Guc dalgalanmalari depolama arizalarini artirdi.

Adimlar:
- Guc sistemi bagimliligini varliga ekle.
- Olay kanitlariyla risk olustur.
- Azaltma: UPS iyilestirmesi ve izleme.
- Stabil olana kadar aylik gozden gecir.

Sonuc: Ariza sikligi dustu ve artik risk kabul edildi.

### Vaka Calismasi 5: Kimlik Avciligi Kampanyasi

Baglam: Birden fazla kullanici MFA hedefli e-postalar bildirdi.

Adimlar:
- Kimlik avciligi icin zafiyet ac.
- Olasilik artisi nedeniyle risk skorunu guncelle.
- Azaltma: farkindalik egitimi ve simule test.
- KRI: tiklama oranini takip et.

Sonuc: Tiklama oranı %60 azaldi.

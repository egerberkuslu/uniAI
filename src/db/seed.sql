-- Seed data for rbac_rag_db
-- Run AFTER schema.sql

-- =============================================
-- ROLES
-- =============================================
INSERT INTO roles (id, name, description, level) VALUES
    (1, 'admin',   'Full access to all resources',    3),
    (2, 'manager', 'Access to department resources',   2),
    (3, 'viewer',  'Access to own resources only',     1)
ON CONFLICT (id) DO NOTHING;

-- =============================================
-- USERS
-- =============================================
INSERT INTO users (id, name, email, role_id, department, token) VALUES
    (1, 'Alice Chen',     'alice@co.com',   1, 'all',         'admin_token'),
    (2, 'Bob Martinez',   'bob@co.com',     2, 'electronics', 'manager_token'),
    (3, 'Charlie Kim',    'charlie@co.com', 3, 'electronics', 'viewer_token'),
    (4, 'Diana Lopez',    'diana@co.com',   2, 'clothing',    'manager2_token'),
    (5, 'Eve Johnson',    'eve@co.com',     3, 'books',       'viewer2_token')
ON CONFLICT (id) DO NOTHING;

-- =============================================
-- ROLE PERMISSIONS
-- =============================================
INSERT INTO role_permissions (role_id, resource, action, scope) VALUES
    -- admin: full access
    (1, 'orders',                'read', 'all'),
    (1, 'refunds',               'read', 'all'),
    (1, 'ogrenci_bilgi_sistemi','read', 'all'),
    -- manager: department access
    (2, 'orders',                'read', 'department'),
    (2, 'refunds',               'read', 'department'),
    (2, 'ogrenci_bilgi_sistemi','read', 'department'),
    -- viewer: own records only
    (3, 'orders',                'read', 'own'),
    (3, 'refunds',               'read', 'own'),
    (3, 'ogrenci_bilgi_sistemi','read', 'own')
ON CONFLICT DO NOTHING;

-- =============================================
-- BİLGİ BANKASI DOKÜMANLARI (Üniversite Yönetmelikleri)
-- =============================================
INSERT INTO kb_documents (id, title, content, category, user_id) VALUES
(1, 'Ders Kayıt Yönergesi', 'Öğrenciler her dönem belirlenen kayıt döneminde derslerine kayıt yaptırmalıdır. Onur öğrencileri ve son sınıf öğrencileri için erken kayıt imkanı bulunmaktadır. Tam zamanlı öğrencilik için minimum 12 kredi, maksimum 18 kredi alınmalıdır. Fazla yük talepleri (19+ kredi) danışman onayı ve minimum 3.5 not ortalaması gerektirir. İlk iki hafta içinde yapılan ders bırakma işlemlerinde ceza uygulanmaz. İkinci haftadan sonra yapılan çekilmeler için W notu verilir ve program başına 6 ders çekilme limitine dahil edilir. Kayıt engelleri ders kaydını engelleyecektir ve ilgili birim (Mali İşler, Akademik İşler veya Öğrenci İşleri) aracılığıyla çözülmelidir. İleri seviye derslere kaydolmadan önce ön koşul derslerden en az C- notu alınmış olmalıdır.', 'akademik_politika', NULL),

(2, 'Notlandırma Sistemi ve Akademik Durum', 'Üniversitemiz 4.0 üzerinden not ortalaması sistemi kullanmaktadır. Harf notları: A (4.0), A- (3.7), B+ (3.3), B (3.0), B- (2.7), C+ (2.3), C (2.0), C- (1.7), D+ (1.3), D (1.0), F (0.0). Öğrenciler iyi akademik durum için minimum 2.0 genel not ortalamasını korumalıdır. 2.0''ın altındaki not ortalaması bir dönem akademik şartlı duruma neden olur. Şartlı durumdan sonra not ortalamasını 2.0''ın üzerine çıkaramayanlar akademik uzaklaştırma cezası alır. Dekanlık Onur Listesi için 12+ kredili dönemde 3.5+ not ortalaması gereklidir. Mezuniyet onur dereceleri: Cum Laude (3.5-3.69), Magna Cum Laude (3.7-3.89), Summa Cum Laude (3.9-4.0). Eksik notlar bir dönem içinde tamamlanmalı, aksi takdirde F''ye dönüşür. Başarılı/Başarısız notlandırma sadece seçmeli dersler için geçerlidir, dönem başına maksimum 2 ders.', 'akademik_politika', NULL),

(3, 'Mezuniyet Gereksinimleri', 'Lisans programları bölüme göre 120-128 kredi gerektirir. Genel eğitim gereksinimleri: 12 kredi Yazılı İletişim, 6 kredi Matematik, 12 kredi laboratuvar içeren Fen Bilimleri, 12 kredi Sosyal Bilimler, 12 kredi Beşeri Bilimler, 6 kredi Sanat, ve 3 kredi Beden Eğitimi veya Sağlık. Bölüm gereksinimleri: Bilgisayar Mühendisliği (48 kredi), Mühendislik (60 kredi), İşletme (54 kredi), Biyoloji (52 kredi). Son yılda bitirme projesi veya tez zorunludur. Öğrenciler minimum 2.0 genel not ortalaması ve 2.5 bölüm not ortalamasına ulaşmalıdır. İkamet zorunluluğu: en az 30 kredi bu üniversitede tamamlanmalıdır. Mezuniyet başvurusu Bahar mezuniyeti için 1 Ekim, Güz mezuniyeti için 1 Mart tarihine kadar yapılmalıdır. Diploma yılda üç kez verilir: Aralık, Mayıs ve Ağustos.', 'mezuniyet', NULL),

(4, 'Mali Yardım ve Burslar', 'Devlet mali yardım başvuru son tarihi öncelikli değerlendirme için 15 Mart''tır. Yardım paketleri hibe, çalışma-öğrenme programı ve devlet kredileri içerebilir. Öğrenciler Tatmin Edici Akademik İlerleme koşullarını karşılamalıdır: %67 ders tamamlama oranı ve minimum 2.0 not ortalaması. Başarı bursları lise not ortalaması ve sınav puanlarına göre 5.000 TL ile tam burs arasında değişir. Rektörlük Bursu 3.9+ not ortalaması ve 1450+ SAT puanı gerektirir. Dekanlık Bursu 3.7+ not ortalaması ve 1350+ SAT puanı gerektirir. Yenileme için yıllık 3.5+ not ortalaması şarttır. İhtiyaç bazlı hibeler kanıtlanmış mali ihtiyacı olan öğrencilere verilir. Çalışma-öğrenme pozisyonları haftada 10-15 saat, saat başı 15 TL ödeme sunar. Öğrenim ücreti ödeme planları dönem ücretlerinin 4 aylık taksitte ödenmesine izin verir. Geç ödeme 100 TL ceza ve kayıt engeline neden olur. İade takvimi: derslerin başlamasından önce %100, 1. hafta %80, 2. hafta %60, 3-4. hafta %40, 4. haftadan sonra %0.', 'mali', NULL),

(5, 'Öğrenci Davranış Kuralları', 'Akademik dürüstlük üniversite misyonunun temelidir. İntihal, kopya çekme ve izinsiz işbirliği yasaktır. İlk ihlal: Ödevde F notu ve akademik dürüstlük semineri. İkinci ihlal: Derste F notu ve disiplin şartı. Üçüncü ihlal: uzaklaştırma veya çıkarma. Tüm ihlaller Öğrenci Davranışları Ofisine bildirilir. Öğrenciler 10 iş günü içinde itiraz hakkına sahiptir. Sınıf davranışı: Zamanında gelin, elektronik cihazları sessize alın, saygılı bir şekilde katılın. Devam politikası öğretim üyesine göre değişir ancak genellikle dönem başına 3 devamsızlığa izin verilir. Taciz, ayrımcılık ve şiddet yasaktır ve derhal disiplin işlemine tabi tutulur. Alkol 21 yaş altı öğrenciler için ve tüm akademik binalarda yasaktır. Sigara ve elektronik sigara tüm kampüs binalarının 25 metre yakınında yasaktır. İhlaller uyarıdan çıkarmaya kadar değişen yaptırımlarla öğrenci davranış süreciyle ele alınır.', 'davranis', NULL),

(6, 'Yurt ve Konaklama Hizmetleri', 'Tüm birinci sınıf öğrencileri 30 mil içinde ailesiyle yaşamıyorsa kampüste kalmalıdır. Yurt başvuruları 200 TL depozito ile 1 Şubat''ta açılır. Oda tipleri: geleneksel çift kişilik (yıllık 8.500 TL), tek kişilik (yıllık 11.000 TL), suit (yıllık 9.500 TL), daire tipi (yıllık 10.500 TL). Yemek planları tüm kampüste kalan öğrenciler için zorunludur. Yurtlar ilgi alanlarına göre düzenlenmiştir: Onur Yurdu, STEM Evi, Sanat ve Kültür, Sessiz Çalışma, Sağlıklı Yaşam. Sessiz saatler: hafta içi 22:00-08:00, hafta sonları gece yarısı-10:00. Her zaman nezaket saatleri geçerlidir. Oda değişiklikleri ilk 4 haftadan sonra Yurt Yaşam Ofisi onayı ile yapılabilir. Yaz yurdu 12 hafta için 1.200 TL''dir. Misafirler oda arkadaşı onayı ile maksimum 3 ardışık gece kalabilir. Karşı cinsiyetten gelen gece misafirler kayıt altına alınmalıdır. Evcil hayvanlar hizmet hayvanları ve maksimum 10 galonluk tankta balık hariç yasaktır.', 'yurt', NULL),

(7, 'Ders Bırakma ve Eğitime Ara Verme', 'Ders bırakma son tarihleri: 2. hafta - kayıt yok, 3-10. hafta - dekan onayı ile W notu, 10. haftadan sonra - belgelenmiş acil durumlar hariç WF notu. Tıbbi çekilmeler sağlık hizmeti sağlayıcısından belge gerektirir ve iade takvimindeki harç iadesine hak kazandırır. Eğitime Ara Verme öğrencilerin öğrenci statülerini koruyarak çalışmalarına 2 döneme kadar geçici olarak ara vermelerine olanak tanır. Onaylanan nedenler: tıbbi durumlar, askerlik hizmeti, aile acil durumları veya kişisel koşullar. Başvuru, Öğrenci Dekanına destekleyici belgelerle birlikte sunulmalıdır. Ara verme sırasında öğrenciler derslere katılamaz veya kampüs tesislerini kullanamazlar. Ara verme koşulları karşılanırsa geri dönüşte yeniden kayıt garanti edilir. Mali yardım etkileri: federal yardım ödemesiz dönem süresi etkilenebilir. Uluslararası öğrenciler ara vermeden önce vize durumu etkileri hakkında Uluslararası Öğrenci Hizmetlerine danışmalıdır.', 'akademik_politika', NULL),

(8, 'Sınav Politikaları ve Final Sınavları', 'Final sınav dönemi dönem sonunda 5 gün sürer. Final haftasında ders yapılmaz. Sınav programı final başlamadan 4 hafta önce yayınlanır. Bir günde 3''ten fazla sınavı olan öğrenciler program ayarlaması talep edebilir. Mazeret sınavları öğretim üyesi onayı ve belgelenmiş geçerli neden gerektirir (doktor notu ile hastalık, aile acil durumu, dini gözlem). Sınav çakışmaları program yayınlandıktan sonra 48 saat içinde Öğrenci İşlerine bildirilmelidir. Sınavlar sırasında: 10 dakika erken gelin, öğrenci kimliği getirin, sadece onaylı materyalleri kullanın, tüm elektronik cihazları sessize alın. Akademik uyarlamalar (ek süre, ayrı oda) en az 2 hafta önceden Engelli Öğrenci Hizmetleri aracılığıyla ayarlanmalıdır. Ev ödevleri ve raporlar için kesin son tarihler vardır; geç teslimler gün başına %10 indirim alır. Kümülatif finaller ders notunun %20-40''ını oluşturur, müfredata bağlı olarak. Sınav saklama: finaller öğrenci talebi üzerine inceleme için bir dönem saklanır.', 'akademik_politika', NULL)
ON CONFLICT (id) DO NOTHING;

-- Update sequence to continue from the highest ID
SELECT setval('kb_documents_id_seq', (SELECT MAX(id) FROM kb_documents));

-- =============================================
-- ORDERS (10 records)
-- =============================================
INSERT INTO orders (id, customer_name, amount, status, department, assigned_to, created_at) VALUES
    (101, 'John Doe',    299.99, 'shipped',    'electronics', 3, '2025-12-15'),
    (102, 'Jane Smith',  149.50, 'delivered',  'electronics', 2, '2025-12-18'),
    (103, 'Mike Wilson',  89.99, 'processing', 'clothing',    4, '2026-01-02'),
    (104, 'Sara Lee',    524.00, 'delivered',  'electronics', 3, '2026-01-10'),
    (105, 'Tom Brown',    67.25, 'shipped',    'books',       5, '2026-01-15'),
    (106, 'Lisa Park',   199.99, 'returned',   'electronics', 2, '2026-02-01'),
    (107, 'Alex Wong',   445.00, 'delivered',  'clothing',    4, '2026-02-10'),
    (108, 'Emma Davis',  112.50, 'processing', 'electronics', 3, '2026-03-01'),
    (109, 'Ryan Chen',   334.75, 'shipped',    'electronics', 2, '2026-03-05'),
    (110, 'Mia Taylor',   78.00, 'delivered',  'books',       5, '2026-03-10')
ON CONFLICT (id) DO NOTHING;

-- =============================================
-- REFUNDS (6 records)
-- =============================================
INSERT INTO refunds (id, order_id, customer_name, amount, reason, department, processed_by, created_at) VALUES
    (201, 106, 'Lisa Park',   199.99, 'Defective product',        'electronics', 2, '2026-02-05'),
    (202, 103, 'Mike Wilson',  89.99, 'Wrong size',               'clothing',    4, '2026-01-20'),
    (203, 101, 'John Doe',    299.99, 'Changed mind',             'electronics', 3, '2026-01-10'),
    (204, 107, 'Alex Wong',   445.00, 'Late delivery',            'clothing',    4, '2026-02-25'),
    (205, 104, 'Sara Lee',    150.00, 'Partial refund - damaged', 'electronics', 2, '2026-02-15'),
    (206, 110, 'Mia Taylor',   78.00, 'Wrong item',               'books',       5, '2026-03-15')
ON CONFLICT (id) DO NOTHING;

-- =============================================
-- OGRENCI BILGI SISTEMI (Student Information System)
-- =============================================
INSERT INTO ogrenci_bilgi_sistemi (id, student_number, full_name, email, bolum, sinif, gpa, advisor, advisor_id) VALUES
    (301, '2025001', 'Mert Yilmaz',     'mert@uni.edu',     'electronics', 4, 3.42, 'Bob Martinez',   2),
    (302, '2025002', 'Selin Acar',      'selin@uni.edu',    'electronics', 3, 3.78, 'Bob Martinez',   2),
    (303, '2025003', 'Ahmet Kaya',      'ahmet@uni.edu',    'clothing',    2, 2.95, 'Diana Lopez',    4),
    (304, '2025004', 'Ece Demir',       'ece@uni.edu',      'clothing',    1, 3.10, 'Diana Lopez',    4),
    (305, '2025005', 'Burak Can',       'burak@uni.edu',    'books',       4, 3.90, 'Eve Johnson',    5),
    (306, '2025006', 'Deniz Karaca',    'deniz@uni.edu',    'electronics', 2, 3.05, 'Charlie Kim',    3)
ON CONFLICT (id) DO NOTHING;

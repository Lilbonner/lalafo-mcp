package main

import (
	"regexp"
	"strings"
)

const carcheckNote = "Carcheck — госсервис с входом и reCAPTCHA, автоматическая проверка невозможна. " +
	"Откройте ссылку, при необходимости вставьте госномер и пройдите капчу. " +
	"Проверяются только номера, выданные в КР (формат вроде 01KG555BRQ)."

var (
	plateStripRe = regexp.MustCompile(`[^0-9A-Za-zА-Яа-я]`)
	plateRe      = regexp.MustCompile(`^[0-9A-ZА-Я]{6,12}$`)
)

func normalizePlate(raw string) string {
	return strings.ToUpper(plateStripRe.ReplaceAllString(raw, ""))
}

func plausiblePlate(p string) bool {
	return plateRe.MatchString(p)
}

type FineLink struct {
	Service string `json:"service"`
	URL     string `json:"url"`
}

type FineResult struct {
	PlateInput      string     `json:"plate_input"`
	PlateNormalized string     `json:"plate_normalized"`
	ValidFormat     bool       `json:"valid_format"`
	Links           []FineLink `json:"links"`
	Note            string     `json:"note"`
}

func buildLinks(plate string) []FineLink {
	services := [][2]string{
		{"carcheck.gov.kg — официальный (ГРС)", "https://carcheck.gov.kg/ru"},
		{"mashina.kg — история по госномеру", "https://m.mashina.kg/carcheck/"},
		{"tolom.kg — проверка штрафов", "https://tolom.kg/"},
		{"balance.kg — проверка/оплата штрафов", "https://balance.kg/"},
	}
	out := make([]FineLink, 0, len(services))
	for _, s := range services {
		u := s[1]
		if plate != "" && strings.Contains(u, "carcheck.gov.kg") {
			u += "?number=" + plate
		}
		out = append(out, FineLink{Service: s[0], URL: u})
	}
	return out
}
